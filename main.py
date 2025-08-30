from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import tempfile
import os
import asyncio
from datetime import datetime
import logging
from typing import Optional
import weasyprint
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SEO Report PDF Renderer",
    description="Convert HTML reports to PDF with custom styling",
    version="1.0.0"
)

class HTMLRequest(BaseModel):
    html: str
    filename: Optional[str] = None
    orientation: Optional[str] = "portrait"  # portrait or landscape
    format: Optional[str] = "A4"  # A4, A3, Letter
    margin: Optional[str] = "16mm"
    
class RenderResponse(BaseModel):
    success: bool
    message: str
    file_size: Optional[int] = None

# CSS voor PDF optimalisaties
PDF_CSS = """
@page {
    size: A4;
    margin: 16mm;
    @top-center {
        content: "";
    }
    @bottom-center {
        content: counter(page);
        font-family: Inter, system-ui, sans-serif;
        font-size: 10pt;
        color: #6b7280;
    }
}

body {
    font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    line-height: 1.4;
    color: #0E1331;
}

/* Print-specific optimizations */
.page {
    page-break-after: auto;
    min-height: unset;
}

.sg {
    break-inside: avoid;
    page-break-inside: avoid;
}

.block {
    break-inside: avoid;
}

table {
    break-inside: avoid;
}

.kpi-list {
    break-inside: avoid;
}

/* Ensure proper spacing */
.wrap {
    padding: 0;
}

.header {
    margin-bottom: 20px;
}

.footer {
    position: static;
    margin-top: 20px;
    border-top: 1px solid #E7E9F3;
    padding-top: 10px;
}

/* Color adjustments for print */
.kpi.good .v { color: #22c55e !important; }
.kpi.warning .v { color: #f59e0b !important; }
.kpi.danger .v { color: #ef4444 !important; }

.badge.high { background: #ef4444 !important; }
.badge.medium { background: #f59e0b !important; }
.badge.low { background: #22c55e !important; }
"""

def clean_html_for_pdf(html_content: str) -> str:
    """Clean and optimize HTML for PDF rendering"""
    
    # Remove any problematic elements
    html_content = html_content.replace('page-break-after: always;', '')
    
    # Ensure proper HTML structure
    if not html_content.startswith('<!DOCTYPE html>'):
        html_content = '<!DOCTYPE html>\n' + html_content
    
    # Add PDF-specific CSS
    css_insertion_point = '</style>'
    if css_insertion_point in html_content:
        html_content = html_content.replace(
            css_insertion_point, 
            PDF_CSS + '\n</style>'
        )
    else:
        # If no style tag found, add CSS before </head>
        html_content = html_content.replace(
            '</head>',
            f'<style>{PDF_CSS}</style>\n</head>'
        )
    
    return html_content

@app.get("/")
async def root():
    return {
        "service": "SEO Report PDF Renderer",
        "version": "1.0.0",
        "endpoints": {
            "render": "POST /render - Convert HTML to PDF",
            "health": "GET /health - Health check"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/render")
async def render_pdf(request: HTMLRequest):
    """
    Convert HTML to PDF and return as downloadable file
    """
    try:
        logger.info(f"Starting PDF render for {len(request.html)} chars of HTML")
        
        # Validate HTML input
        if not request.html or len(request.html.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="HTML content is too short or empty"
            )
        
        # Clean HTML for PDF rendering
        cleaned_html = clean_html_for_pdf(request.html)
        
        # Generate filename
        if request.filename:
            filename = request.filename.replace('.pdf', '') + '.pdf'
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"seo_report_{timestamp}.pdf"
        
        # Configure PDF options
        font_config = FontConfiguration()
        
        # Create CSS string for page settings
        page_css = f"""
        @page {{
            size: {request.format} {request.orientation};
            margin: {request.margin};
        }}
        """
        
        # Render PDF
        try:
            html_doc = HTML(string=cleaned_html)
            css_doc = CSS(string=page_css, font_config=font_config)
            
            # Generate PDF in memory
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc], font_config=font_config)
            
            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            
            # Return PDF as streaming response
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Length": str(len(pdf_bytes))
                }
            )
            
        except Exception as render_error:
            logger.error(f"PDF rendering failed: {str(render_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"PDF rendering failed: {str(render_error)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in render_pdf: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/render-preview")
async def render_preview(request: HTMLRequest):
    """
    Render PDF and return base64 encoded preview (for testing)
    """
    try:
        import base64
        
        logger.info("Starting PDF preview render")
        
        # Clean HTML
        cleaned_html = clean_html_for_pdf(request.html)
        
        # Configure PDF
        font_config = FontConfiguration()
        page_css = f"""
        @page {{
            size: {request.format} {request.orientation};
            margin: {request.margin};
        }}
        """
        
        # Render PDF
        html_doc = HTML(string=cleaned_html)
        css_doc = CSS(string=page_css, font_config=font_config)
        pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc], font_config=font_config)
        
        # Return base64 encoded PDF
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        return {
            "success": True,
            "pdf_base64": pdf_base64,
            "file_size": len(pdf_bytes),
            "pages_estimated": max(1, len(pdf_bytes) // 50000)  # Rough estimate
        }
        
    except Exception as e:
        logger.error(f"Preview render failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Preview render failed: {str(e)}"
        )

@app.post("/validate-html")
async def validate_html(request: HTMLRequest):
    """
    Validate HTML structure before rendering
    """
    try:
        html_content = request.html.strip()
        
        validation_results = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "stats": {
                "length": len(html_content),
                "has_doctype": html_content.startswith('<!DOCTYPE') or html_content.startswith('<!doctype'),
                "has_html_tag": '<html' in html_content.lower(),
                "has_head_tag": '<head' in html_content.lower(),
                "has_body_tag": '<body' in html_content.lower(),
                "has_styles": '<style' in html_content.lower()
            }
        }
        
        # Check for common issues
        if len(html_content) < 100:
            validation_results["issues"].append("HTML content is very short")
            validation_results["valid"] = False
            
        if not validation_results["stats"]["has_html_tag"]:
            validation_results["warnings"].append("Missing <html> tag")
            
        if not validation_results["stats"]["has_head_tag"]:
            validation_results["warnings"].append("Missing <head> tag")
            
        if not validation_results["stats"]["has_body_tag"]:
            validation_results["issues"].append("Missing <body> tag")
            validation_results["valid"] = False
            
        if not validation_results["stats"]["has_styles"]:
            validation_results["warnings"].append("No inline styles found - PDF may look unstyled")
        
        return validation_results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"HTML validation failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )

# Requirements.txt content (add this as a separate file):
"""
fastapi==0.104.1
uvicorn[standard]==0.24.0
weasyprint==60.2
pydantic==2.5.0
"""
