from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import weasyprint
from datetime import datetime
import tempfile
import os
from typing import Dict, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SEO Report PDF Generator", version="1.0.0")

class ReportData(BaseModel):
    html: str
    metadata: Dict[str, Any]
    filename: Optional[str] = None
    pdf_options: Optional[Dict[str, Any]] = None

def generate_filename(metadata: Dict[str, Any], custom_filename: str = None) -> str:
    """Generate a proper filename for the PDF"""
    if custom_filename:
        # Ensure it ends with .pdf
        if not custom_filename.endswith('.pdf'):
            custom_filename += '.pdf'
        return custom_filename
    
    # Generate filename from metadata
    scan_id = metadata.get('scanId', 'unknown')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    return f"seo_audit_{scan_id}_{timestamp}.pdf"

def sanitize_html(html_content: str) -> str:
    """Clean up HTML for better PDF rendering"""
    # Add any HTML sanitization/optimization here
    # For now, just ensure proper encoding
    if not html_content.strip().startswith('<!DOCTYPE'):
        html_content = '<!DOCTYPE html>\n' + html_content
    
    return html_content

@app.get("/")
def read_root():
    return {
        "message": "SEO Report PDF Generator API", 
        "version": "1.0.0",
        "endpoints": {
            "/generate-pdf": "POST - Generate PDF from HTML",
            "/health": "GET - Health check"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/generate-pdf")
async def generate_pdf(report_data: ReportData):
    """Generate PDF from HTML content with proper filename"""
    
    try:
        # Validate input
        if not report_data.html:
            raise HTTPException(status_code=400, detail="HTML content is required")
        
        # Sanitize HTML
        clean_html = sanitize_html(report_data.html)
        
        # Generate filename
        filename = generate_filename(report_data.metadata, report_data.filename)
        
        # PDF generation options
        pdf_options = report_data.pdf_options or {}
        
        # Default WeasyPrint options
        default_options = {
            'presentational_hints': True,
            'optimize_images': True,
        }
        default_options.update(pdf_options)
        
        logger.info(f"Generating PDF: {filename}")
        
        # Create temporary file for HTML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
            temp_html.write(clean_html)
            temp_html_path = temp_html.name
        
        try:
            # Generate PDF using WeasyPrint
            pdf_document = weasyprint.HTML(filename=temp_html_path).write_pdf(**default_options)
            
            logger.info(f"PDF generated successfully: {len(pdf_document)} bytes")
            
            # Return PDF as response with proper headers
            return Response(
                content=pdf_document,
                media_type='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': str(len(pdf_document)),
                    'X-Generated-At': datetime.now().isoformat(),
                    'X-Scan-ID': report_data.metadata.get('scanId', 'unknown')
                }
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_html_path):
                os.unlink(temp_html_path)
    
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.post("/generate-pdf-base64")
async def generate_pdf_base64(report_data: ReportData):
    """Generate PDF and return as base64 string (alternative endpoint)"""
    import base64
    
    try:
        # Generate PDF using the same logic
        clean_html = sanitize_html(report_data.html)
        filename = generate_filename(report_data.metadata, report_data.filename)
        
        pdf_options = report_data.pdf_options or {}
        default_options = {
            'presentational_hints': True,
            'optimize_images': True,
        }
        default_options.update(pdf_options)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
            temp_html.write(clean_html)
            temp_html_path = temp_html.name
        
        try:
            pdf_document = weasyprint.HTML(filename=temp_html_path).write_pdf(**default_options)
            pdf_base64 = base64.b64encode(pdf_document).decode('utf-8')
            
            return {
                "pdf_base64": pdf_base64,
                "filename": filename,
                "size_bytes": len(pdf_document),
                "generated_at": datetime.now().isoformat(),
                "scan_id": report_data.metadata.get('scanId', 'unknown')
            }
            
        finally:
            if os.path.exists(temp_html_path):
                os.unlink(temp_html_path)
    
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Use PORT env var from Render, fallback to 8000 for local development
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
