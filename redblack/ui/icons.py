"""Ícones vetoriais próprios (SVG inline, traço simples 24x24)."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "bolear": '<path d="M4 20V10a6 6 0 0 1 6-6h10"/><path d="M4 20h16V4" stroke-dasharray="2 2"/>',
    # Barras de organizar/ferramentas (desenhos próprios)
    "machine": '<path d="M14 6a4 4 0 0 0 5 5l-9 9a2 2 0 0 1-3-3l9-9a4 4 0 0 0-2-2z"/><path d="M15 3l2 2-1 1"/>',
    "pan": '<path d="M12 2v20M2 12h20M12 2l-3 3M12 2l3 3M12 22l-3-3M12 22l3-3M2 12l3-3M2 12l3 3M22 12l-3-3M22 12l-3 3"/>',
    "zoom_sel": '<rect x="3" y="3" width="11" height="11" stroke-dasharray="2 2"/><circle cx="14" cy="14" r="4"/><path d="M17 17l4 4"/>',
    "group": '<rect x="3" y="3" width="18" height="18" stroke-dasharray="2 2"/><rect x="6" y="6" width="6" height="6"/><circle cx="15" cy="15" r="3"/>',
    "ungroup": '<rect x="3" y="3" width="8" height="8"/><circle cx="17" cy="17" r="4"/><path d="M14 6h7M6 14v7"/>',
    "flip_h": '<path d="M12 3v18" stroke-dasharray="2 2"/><path d="M10 6L3 18h7z"/><path d="M14 6l7 12h-7z"/>',
    "flip_v": '<path d="M3 12h18" stroke-dasharray="2 2"/><path d="M6 10L18 3v7z"/><path d="M6 14l12 7v-7z"/>',
    "mirror_line": '<path d="M3 21L21 3" stroke-dasharray="2 2"/><path d="M4 12l6-6 0 6z"/><path d="M12 20l6-6-6 0z"/>',
    "align_left": '<path d="M4 3v18"/><rect x="6" y="5" width="12" height="5"/><rect x="6" y="14" width="7" height="5"/>',
    "align_hcenter": '<path d="M12 3v18"/><rect x="5" y="5" width="14" height="5"/><rect x="8" y="14" width="8" height="5"/>',
    "align_right": '<path d="M20 3v18"/><rect x="6" y="5" width="12" height="5"/><rect x="11" y="14" width="7" height="5"/>',
    "align_top": '<path d="M3 4h18"/><rect x="5" y="6" width="5" height="12"/><rect x="14" y="6" width="5" height="7"/>',
    "align_vcenter": '<path d="M3 12h18"/><rect x="5" y="5" width="5" height="14"/><rect x="14" y="8" width="5" height="8"/>',
    "align_bottom": '<path d="M3 20h18"/><rect x="5" y="6" width="5" height="12"/><rect x="14" y="11" width="5" height="7"/>',
    "align_centers": '<circle cx="12" cy="12" r="7"/><path d="M12 2v6M12 16v6M2 12h6M16 12h6"/>',
    "dist_h": '<path d="M3 3v18M21 3v18"/><rect x="9" y="7" width="6" height="10"/>',
    "dist_v": '<path d="M3 3h18M3 21h18"/><rect x="7" y="9" width="10" height="6"/>',
    "offset": '<rect x="8" y="8" width="8" height="8"/><rect x="3" y="3" width="18" height="18" rx="4"/>',
    "weld": '<path d="M3 9h6V3h12v12h-6v6H3z"/>',
    "union": '<rect x="3" y="3" width="12" height="12"/><rect x="9" y="9" width="12" height="12"/>',
    "subtract": '<path d="M3 3h12v6H9v6H3z"/><rect x="9" y="9" width="12" height="12" stroke-dasharray="2 2"/>',
    "intersect": '<rect x="3" y="3" width="12" height="12" stroke-dasharray="2 2"/><rect x="9" y="9" width="12" height="12" stroke-dasharray="2 2"/><rect x="9" y="9" width="6" height="6"/>',
    "grid_array": '<rect x="3" y="3" width="5" height="5"/><rect x="10" y="3" width="5" height="5"/><rect x="17" y="3" width="4" height="5"/><rect x="3" y="10" width="5" height="5"/><rect x="10" y="10" width="5" height="5"/><rect x="17" y="10" width="4" height="5"/><rect x="3" y="17" width="5" height="4"/><rect x="10" y="17" width="5" height="4"/>',
    "circ_array": '<circle cx="12" cy="4" r="2"/><circle cx="19" cy="9" r="2"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/><circle cx="5" cy="9" r="2"/>',
    "copy_path": '<path d="M3 19C7 5 17 19 21 5" stroke-dasharray="2 2"/><rect x="2" y="15" width="4" height="4"/><rect x="10" y="10" width="4" height="4"/><rect x="18" y="3" width="4" height="4"/>',
    "star": '<path d="M12 2l3 7h7l-5.5 4.5 2 7.5L12 16.5 5.5 21l2-7.5L2 9h7z"/>',
    "trim": '<circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8 16L20 4M16 16L4 4"/>',
    "anchor": '<circle cx="12" cy="5" r="2"/><path d="M12 7v14M8 11h8M5 14a7 7 0 0 0 14 0"/>',
    "new": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "open": '<path d="M3 7h6l2 2h10v10H3z"/>',
    "save": '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8V3"/><rect x="8" y="14" width="8" height="5"/>',
    "import": '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M4 21h16"/>',
    "export": '<path d="M12 15V3"/><path d="M7 8l5-5 5 5"/><path d="M4 21h16"/>',
    "undo": '<path d="M4 7h10a6 6 0 0 1 0 12H8"/><path d="M8 3L4 7l4 4"/>',
    "redo": '<path d="M20 7H10a6 6 0 0 0 0 12h6"/><path d="M16 3l4 4-4 4"/>',
    "copy": '<rect x="8" y="8" width="12" height="12"/><path d="M4 16V4h12"/>',
    "paste": '<rect x="5" y="4" width="14" height="17"/><rect x="9" y="2" width="6" height="4"/>',
    "delete": '<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15"/>',
    "zoom_in": '<circle cx="10" cy="10" r="7"/><path d="M15 15l6 6M7 10h6M10 7v6"/>',
    "zoom_out": '<circle cx="10" cy="10" r="7"/><path d="M15 15l6 6M7 10h6"/>',
    "zoom_fit": '<path d="M3 8V3h5M16 3h5v5M21 16v5h-5M8 21H3v-5"/><rect x="8" y="8" width="8" height="8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9L7 7M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "select": '<path d="M5 3l14 9-6 1-3 6z"/>',
    "node": '<path d="M4 18C8 4 16 20 20 6"/><rect x="2" y="16" width="4" height="4"/><rect x="18" y="4" width="4" height="4"/>',
    "pen": '<path d="M4 20l4-1 11-11-3-3L5 16z"/>',
    "rect": '<rect x="4" y="6" width="16" height="12"/>',
    "ellipse": '<ellipse cx="12" cy="12" rx="9" ry="6"/>',
    "polygon": '<path d="M12 3l9 7-3 10H6L3 10z"/>',
    "text": '<path d="M5 20L12 4l7 16M8 14h8"/>',
    "measure": '<path d="M3 17L17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>',
    "layers": '<path d="M3 7l9-4 9 4-9 4z"/><path d="M3 12l9 4 9-4M3 17l9 4 9-4"/>',
    "material": '<rect x="3" y="5" width="18" height="14"/><path d="M3 10h18M8 5v14"/>',
    "connect": '<path d="M9 7V3M15 7V3M6 7h12v5a6 6 0 0 1-12 0zM12 18v4"/>',
    "home": '<path d="M3 11l9-8 9 8M5 9v12h14V9"/>',
    "origin": '<circle cx="12" cy="12" r="4"/><path d="M12 2v6M12 16v6M2 12h6M16 12h6"/>',
    "frame": '<rect x="4" y="4" width="16" height="16" stroke-dasharray="3 2"/>',
    "play": '<path d="M7 4l13 8-13 8z"/>',
    "pause": '<path d="M8 4v16M16 4v16"/>',
    "stop": '<rect x="5" y="5" width="14" height="14"/>',
    "air": '<path d="M3 8h11a3 3 0 1 0-3-3M3 16h15a3 3 0 1 1-3 3M3 12h18"/>',
    "up": '<path d="M12 20V4M5 11l7-7 7 7"/>',
    "down": '<path d="M12 4v16M5 13l7 7 7-7"/>',
    "left": '<path d="M20 12H4M11 5l-7 7 7 7"/>',
    "right": '<path d="M4 12h16M13 5l7 7-7 7"/>',
    "snap": '<rect x="3" y="3" width="8" height="8"/><circle cx="11" cy="11" r="2.5"/><path d="M14 14l7 7M17 21h4v-4"/>',
    "preview":'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "info":'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.5"/>',
    # comandos de contorno (barra da esquerda)
    "juntar": '<path d="M3 18l6-9"/><path d="M15 9l6 9"/><circle cx="12" cy="7" r="2.2"/><path d="M9 9l1.5-1.2M15 9l-1.5-1.2"/>',
    "fechar_caminho": '<path d="M5 19V6h14v13H9"/><circle cx="5" cy="19" r="1.8"/><circle cx="9" cy="19" r="1.8"/>',
    "duplicados": '<rect x="3" y="3" width="11" height="11"/><rect x="10" y="10" width="11" height="11" stroke-dasharray="2 2"/><path d="M16 4l4 4M20 4l-4 4"/>',
    "inverter_dir": '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
    "otimizar": '<path d="M3 17c3-1 3-5 6-5s3 3 6 3 3-6 6-7"/><circle cx="3" cy="17" r="1.3"/><circle cx="21" cy="8" r="1.3"/>',
}

NORMAL = "#e4e6eb"
DISABLED = "#6a6f78"


def _pixmap(name: str, color: str, size: int) -> QPixmap:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
           f'{_PATHS[name]}</svg>')
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    return pm


def icon(name: str) -> QIcon:
    ic = QIcon()
    for size in (24, 48):
        ic.addPixmap(_pixmap(name, NORMAL, size), QIcon.Normal)
        # Ícone desabilitado explícito: o cinza automático do Qt some no tema escuro.
        ic.addPixmap(_pixmap(name, DISABLED, size), QIcon.Disabled)
    return ic
