import streamlit as st
import anthropic
import json
import PyPDF2
from typing import Dict, List
import io
import re

class StyleGuideProcessor:
    """Handles processing of PDF style guides and organizes content into sections."""
    def __init__(self):
        self.sections = {}
        
    def extract_pdf_text(self, pdf_file) -> str:
        """Extracts text content from a PDF file."""
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        full_text = ""
        
        for page in pdf_reader.pages:
            full_text += page.extract_text() + "\n"
            
        return full_text
    
    def process_style_guide(self, text: str) -> Dict[str, str]:
        """Organizes style guide text into sections based on headers."""
        current_section = "General"
        sections = {"General": []}
        
        for line in text.split('\n'):
            if line.isupper() or line.strip().endswith(':'):
                current_section = line.strip().rstrip(':')
                sections[current_section] = []
            else:
                sections[current_section].append(line)
                
        return {k: '\n'.join(v) for k, v in sections.items()}

class ContentFormatter:
    """Handles text formatting and cleaning for various content types."""
    @staticmethod
    def clean_text(text: str) -> str:
        """Removes unwanted formatting and normalizes text output."""
        if isinstance(text, (dict, list)):
            text = str(text)
            
        # Remove any TextBlock formatting
        text = text.replace('[TextBlock(text="', '')
        text = text.replace('", type="text")]', '')
        
        # Replace escape characters with actual line breaks
        text = text.replace('\\n', '\n')
        text = text.replace('\\r', '\r')
        
        # Remove extra quotes and whitespace
        text = text.strip('"\'')
        
        return text.strip()

class TextAnalyzer:
    """Main class for content analysis and generation."""
    def __init__(self, api_key: str):
        """Initializes the analyzer with necessary components."""
        self.client = anthropic.Client(api_key=api_key)
        self.style_guide = {}
        self.formatter = ContentFormatter()
        self.style_processor = StyleGuideProcessor()
    
    def load_style_guide(self, pdf_file) -> Dict[str, str]:
        """Loads and processes a PDF style guide."""
        text = self.style_processor.extract_pdf_text(pdf_file)
        self.style_guide = self.style_processor.process_style_guide(text)
        return self.style_guide
    
    def analyze_text(self, text: str, content_type: str) -> Dict:
        """Analyzes text content and provides structured feedback."""
        style_guide_context = "\n".join([f"{k}: {v[:300]}..." for k, v in self.style_guide.items()]) if self.style_guide else "No style guide loaded."
        
        prompt = f"""
        Analyze this {content_type} content and respond with ONLY a JSON object in the following structure:
        {{
            "overall_assessment": "A detailed evaluation of the overall content quality and effectiveness",
            "style_evaluation": "An analysis of the writing style, tone, and clarity",
            "suggestions": ["Specific suggestion 1", "Specific suggestion 2", "Specific suggestion 3"]
        }}

        Content to analyze:
        {text}

        Style Guidelines:
        {style_guide_context}

        Remember: Respond with only the JSON object, no additional text or explanation.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = str(response.content)
            
            # First attempt: direct JSON parsing
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Second attempt: extract JSON using regex
                try:
                    json_pattern = r'\{[\s\S]*\}'
                    json_match = re.search(json_pattern, response_text)
                    if json_match:
                        json_str = json_match.group()
                        return json.loads(json_str)
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            # Fallback response
            return {
                "overall_assessment": "Analysis completed with formatting issues.",
                "style_evaluation": f"Content analyzed: {text[:100]}...",
                "suggestions": [
                    "Consider reviewing the content for clarity",
                    "Ensure all key points are clearly communicated",
                    "Review formatting and structure"
                ]
            }
                
        except Exception as e:
            return {
                "overall_assessment": f"Analysis error: {str(e)}",
                "style_evaluation": "Unable to complete style evaluation",
                "suggestions": [
                    "Please try again in a moment",
                    "Consider breaking content into smaller sections"
                ]
            }
    
    def generate_text(self, prompt: str, content_type: str) -> str:
        """Generates new content based on prompt and content type."""
        style_guide_context = "\n".join([f"{k}: {v[:300]}..." for k, v in self.style_guide.items()]) if self.style_guide else "No style guide loaded."
        
        generation_prompt = f"""
        Generate {content_type} content following these guidelines:
        
        {style_guide_context}
        
        Requirements:
        - Professional and clear writing style
        - Proper formatting for {content_type}
        - Direct and concise communication
        
        Content prompt:
        {prompt}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                temperature=0.7,
                messages=[{"role": "user", "content": generation_prompt}]
            )
            
            return self.formatter.clean_text(response.content)
            
        except Exception as e:
            st.error(f"Generation error: {str(e)}")
            return "Content generation failed. Please try again."

def create_sidebar(analyzer: TextAnalyzer) -> tuple:
    """Creates the sidebar navigation and controls."""
    st.sidebar.title("Navigation")
    
    # Style Guide Upload
    st.sidebar.header("Style Guide")
    uploaded_file = st.sidebar.file_uploader("Upload Style Guide (PDF)", type="pdf")
    
    if uploaded_file:
        with st.spinner("Processing style guide..."):
            try:
                sections = analyzer.load_style_guide(uploaded_file)
                st.sidebar.success("Style guide loaded successfully!")
            except Exception as e:
                st.sidebar.error(f"Error loading style guide: {str(e)}")
    
    page = st.sidebar.radio("Choose a tool:", 
                           ["Content Generation", "Content Analysis"])
    
    content_type = st.sidebar.selectbox(
        "Select content type:",
        ["Email", "Customer Correspondence", "Technical Documentation", 
         "Marketing Copy", "General Business"]
    )
    
    return page, content_type

def render_generation_page(analyzer: TextAnalyzer, content_type: str):
    """Renders the content generation interface."""
    st.header("Content Generation")
    st.write(f"Generating {content_type} content")
    
    prompt = st.text_area(
        "What would you like to generate?",
        help="Describe the content you want to create. Be specific about tone, length, and key points."
    )
    
    if st.button("Generate Content"):
        with st.spinner("Generating..."):
            try:
                generated_content = analyzer.generate_text(prompt, content_type)
                st.text_area(
                    "Generated Content (Copy-Paste Ready):",
                    value=generated_content,
                    height=400
                )
            except Exception as e:
                st.error(f"An error occurred during generation: {str(e)}")

def render_analysis_page(analyzer: TextAnalyzer, content_type: str):
    """Renders the content analysis interface."""
    st.header("Content Analysis")
    st.write(f"Analyzing {content_type} content")
    
    text_to_analyze = st.text_area(
        "Paste your content for analysis:",
        height=200
    )
    
    if st.button("Analyze Content"):
        with st.spinner("Analyzing..."):
            try:
                analysis = analyzer.analyze_text(text_to_analyze, content_type)
                
                tab1, tab2, tab3 = st.tabs(["Overview", "Detailed Analysis", "Suggestions"])
                
                with tab1:
                    st.subheader("Overall Assessment")
                    st.write(analysis["overall_assessment"])
                    
                with tab2:
                    st.subheader("Style and Tone")
                    st.write(analysis["style_evaluation"])
                    
                with tab3:
                    st.subheader("Improvement Suggestions")
                    for suggestion in analysis["suggestions"]:
                        st.write(f"• {suggestion}")
            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")

def main():
    """Main application entry point."""
    st.title("Professional Content Tool")
    
    # API Key handling
    api_key = st.sidebar.text_input("Enter Claude API key:", type="password")
    
    if not api_key:
        st.warning("Please enter your API key to continue.")
        return
    
    try:
        analyzer = TextAnalyzer(api_key)
        
        # Create sidebar navigation with analyzer instance
        page, content_type = create_sidebar(analyzer)
        
        # Render appropriate page
        if page == "Content Generation":
            render_generation_page(analyzer, content_type)
        else:
            render_analysis_page(analyzer, content_type)
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check your API key and try again.")

if __name__ == "__main__":
    main()