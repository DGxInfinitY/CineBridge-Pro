import os
import xml.etree.ElementTree as ET
from datetime import datetime
from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import QMarginsF
from .common import HAS_XXHASH

class ReportGenerator:
    @staticmethod
    def generate_pdf(dest_path, file_data_list, project_name="Unnamed Project", thumbnails=None):
        is_visual = thumbnails is not None
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; margin: 30px; }}
                h1 {{ color: #2980B9; border-bottom: 2px solid #2980B9; padding-bottom: 10px; }}
                .header-info {{ margin-bottom: 20px; font-size: 14px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #eee; padding: 8px; text-align: left; font-size: 11px; vertical-align: middle; }}
                th {{ background-color: #f8f9fa; color: #2980B9; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #fafafa; }}
                .thumb {{ width: 120px; height: 68px; background-color: #000; display: block; }}
                .footer {{ margin-top: 40px; font-size: 10px; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>CineBridge Pro | Transfer Report</h1>
            <div class="header-info">
                <p><b>Project:</b> {project_name}</p>
                <p><b>Completion Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><b>Total Files:</b> {len(file_data_list)}</p>
            </div>
            <table>
                <thead>
                    <tr>
                        {"<th>Preview</th>" if is_visual else ""}
                        <th>Filename</th>
                        <th>Size (MB)</th>
                        <th>Checksum (Hash)</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        """
        total_bytes = 0
        for f in file_data_list:
            size_mb = f.get('size', 0) / (1024*1024); total_bytes += f.get('size', 0)
            thumb_html = ""
            if is_visual:
                b64 = thumbnails.get(f['name'], "")
                if b64: thumb_html = f'<td><img src="data:image/png;base64,{b64}" class="thumb"></td>'
                else: thumb_html = '<td><div class="thumb" style="background:#333;"></div></td>'
            html += f"<tr>{thumb_html}<td>{f['name']}</td><td>{size_mb:.2f}</td><td><code>{f.get('hash', 'N/A')}</code></td><td>✅ OK</td></tr>"
        
        html += f"""
                </tbody>
            </table>
            <p><b>Summary:</b> Total Data {total_bytes/(1024**3):.2f} GB transferred and verified.</p>
            <div class="footer">CineBridge Pro v4.16.5 (Dev) - Professional DIT & Post-Production Suite</div>
        </body>
        </html>
        """
        doc = QTextDocument(); doc.setHtml(html)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(dest_path)
        printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF(15, 15, 15, 15)))
        doc.print(printer); return dest_path

class MHLGenerator:
    @staticmethod
    def generate(dest_root, transfer_data, project_name="CineBridge_Pro"):
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        root = ET.Element("hashlist", version="1.1")
        for f in transfer_data:
            if f.get('hash') == "N/A": continue
            hash_node = ET.SubElement(root, "hash")
            ET.SubElement(hash_node, "file").text = f['name']
            ET.SubElement(hash_node, "size").text = str(f['size'])
            hash_tag = "xxhash64" if HAS_XXHASH else "md5"
            ET.SubElement(hash_node, hash_tag).text = f['hash']
            ET.SubElement(hash_node, "hashdate").text = timestamp
        tree = ET.ElementTree(root)
        if hasattr(ET, 'indent'): ET.indent(tree, space="  ", level=0)
        mhl_path = os.path.join(dest_root, f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mhl")
        tree.write(mhl_path, encoding="utf-8", xml_declaration=True); return mhl_path
