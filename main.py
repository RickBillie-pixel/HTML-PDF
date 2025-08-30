from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import logging
from typing import Optional
import io
from xhtml2pdf import pisa
from reportlab.lib.pagesizes import A4, letter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SEO Report PDF Renderer", version="1.0.0")

class HTMLRequest(BaseModel):
    html: str
    filename: Optional[str] = None
    format: Optional[str] = "A4"

def clean_html_for_pdf(html_content: str) -> str:
    """Clean HTML for xhtml2pdf compatibility"""
    # xhtml2pdf heeft beperkte CSS support
    html_content = html_content.replace('page-break-after: always;', '')
    
    # Voeg PDF-specifieke CSS toe
    pdf_css = """
    <style>
    @page { size: A4; margin: 1cm; }
    body { font-family: Arial, sans-serif; color: #333; }
    .kpi.good .v { color: #22c55e !important; }
    .kpi.warning .v { color: #f59e0b !important; }
    .kpi.danger .v { color: #ef4444 !important; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    </style>
    """
    
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', pdf_css + '</head>')
    
    return html_content

@app.get("/")
async def root():
    return {"service": "SEO Report PDF Renderer", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/render")
async def render_pdf(request: HTMLRequest):
    try:
        logger.info(f"Rendering PDF with xhtml2pdf")
        
        if not request.html or len(request.html.strip()) < 50:
            raise HTTPException(status_code=400, detail="HTML content too short")
        
        cleaned_html = clean_html_for_pdf(request.html)
        
        filename = request.filename or f"seo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        # Render PDF met xhtml2pdf
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(cleaned_html, dest=pdf_buffer)
        
        if pisa_status.err:
            raise HTTPException(status_code=500, detail="PDF generation failed")
        
        pdf_buffer.seek(0)
        pdf_bytes = pdf_buffer.getvalue()
        
        logger.info(f"PDF generated: {len(pdf_bytes)} bytes")
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"PDF render error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
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

.kpi.good .v { color: #22c55e !important; }
.kpi.warning .v { color: #f59e0b !important; }
.kpi.danger .v { color: #ef4444 !important; }

.badge.high { background: #ef4444 !important; }
.badge.medium { background: #f59e0b !important; }
.badge.low { background: #22c55e !important; }
"""

def clean_html_for_pdf(html_content: str) -> str:
    """Clean and optimize HTML for PDF rendering"""
    
    html_content = html_content.replace('page-break-after: always;', '')
    
    if not html_content.startswith('<!DOCTYPE html>'):
        html_content = '<!DOCTYPE html>\n' + html_content
    
    css_insertion_point = '</style>'
    if css_insertion_point in html_content:
        html_content = html_content.replace(
            css_insertion_point, 
            PDF_CSS + '\n</style>'
        )
    else:
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
        "status": "running",
        "endpoints": {
            "render": "POST /render - Convert HTML to PDF",
            "health": "GET /health - Health check"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/render")
async def render_pdf(request: HTMLRequest):
    """Convert HTML to PDF and return as downloadable file"""
    try:
        logger.info(f"Starting PDF render for {len(request.html)} chars of HTML")
        
        if not request.html or len(request.html.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="HTML content is too short or empty"
            )
        
        cleaned_html = clean_html_for_pdf(request.html)
        
        if request.filename:
            filename = request.filename.replace('.pdf', '') + '.pdf'
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"seo_report_{timestamp}.pdf"
        
        font_config = FontConfiguration()
        
        page_css = f"""
        @page {{
            size: {request.format} {request.orientation};
            margin: {request.margin};
        }}
        """
        
        try:
            html_doc = HTML(string=cleaned_html)
            css_doc = CSS(string=page_css, font_config=font_config)
            
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc], font_config=font_config)
            
            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")


