# -*- coding: utf-8 -*-
"""
EVE Online Hacking Copilot — Mapa Relativo em Grafo (PyQt6)

Sem grid fixo. O mapa cresce a partir do nó de entrada enquanto
você revela os nós no jogo. Setas expandem o grafo na direção
que você explorou. O calor vermelho aponta onde o Core está.
"""

import os, re, glob, subprocess, threading, math
from PIL import Image

from PyQt6.QtCore    import Qt, pyqtSignal, QObject, QRect, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QScrollArea, QSizePolicy, QGridLayout
)
from PyQt6.QtGui import (
    QCursor, QPainter, QPen, QBrush, QColor, QFont,
    QPolygon, QPainterPath, QRadialGradient
)

# ──────────────────────────────────────────────────────────────────────────────
# Tipos de nó
# ──────────────────────────────────────────────────────────────────────────────
NODE_HIDDEN   = "hidden"
NODE_EMPTY    = "empty"
NODE_NUM      = "num"
NODE_FIREWALL = "firewall"
NODE_ANTIVIRUS= "antivirus"
NODE_RESTORE  = "restore"
NODE_CACHE    = "cache"
NODE_CORE     = "core"
NODE_SUPPRESS = "suppress"
NODE_START    = "start"

# ──────────────────────────────────────────────────────────────────────────────
# Funções de desenho (QPainter) — tamanho 32×32 px
# ──────────────────────────────────────────────────────────────────────────────

def _draw_hidden(p, r, heat=0.0):
    t = min(max(heat, 0.0), 1.0)
    if t > 0.05:
        bg = QColor(int(28 + t*180), int(30*(1-t)), int(40*(1-t)))
        bc = QColor(int(100+t*155), int(40*(1-t)), int(40*(1-t)))
    else:
        bg, bc = QColor("#1c2128"), QColor("#30363d")
    p.fillRect(r, bg)
    p.setPen(QPen(bc, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    p.setPen(QPen(QColor("#fca5a5" if t>0.5 else "#6e7681"), 1))
    f = QFont("monospace", 11, QFont.Weight.Bold); p.setFont(f)
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, "?")

def _draw_empty(p, r):
    p.fillRect(r, QColor("#161b22"))
    p.setPen(QPen(QColor("#30363d"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#3d4451")))
    p.drawEllipse(cx-3,cy-3,6,6)

def _draw_num(p, r, val):
    p.fillRect(r, QColor("#0d2543"))
    p.setPen(QPen(QColor("#58a6ff"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    rad = min(r.width(),r.height())//2 - 3
    g = QRadialGradient(cx,cy,rad)
    g.setColorAt(0, QColor("#1a5fb4")); g.setColorAt(1, QColor("#0d2543"))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
    p.drawEllipse(cx-rad,cy-rad,rad*2,rad*2)
    p.setPen(QPen(QColor("#58a6ff"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(cx-rad,cy-rad,rad*2,rad*2)
    f = QFont("monospace",12,QFont.Weight.Bold); p.setFont(f)
    p.setPen(QPen(QColor("#a8d8ff"),1))
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(val) if val else "?")

def _draw_firewall(p, r):
    p.fillRect(r, QColor("#2b1e00"))
    p.setPen(QPen(QColor("#d29922"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    bw,bh = 7,4
    for ri,dy in enumerate([-bh,0,bh]):
        off = (bw//2) if ri%2==1 else 0
        for dx in range(-bw*2+off, bw*2+off+1, bw):
            bx=cx+dx-bw//2; by=cy+dy-bh//2
            br=QRect(int(bx),int(by),bw-1,bh-1)
            p.fillRect(br,QColor("#7d4e00"))
            p.setPen(QPen(QColor("#d29922"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(br)

def _draw_antivirus(p, r):
    p.fillRect(r, QColor("#2b1418"))
    p.setPen(QPen(QColor("#f85149"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    w,h = r.width()-10, r.height()-8
    path = QPainterPath()
    path.moveTo(cx-w//2,cy-h//2); path.lineTo(cx+w//2,cy-h//2)
    path.lineTo(cx+w//2,cy); path.quadTo(cx+w//2,cy+h//2,cx,cy+h//2)
    path.quadTo(cx-w//2,cy+h//2,cx-w//2,cy); path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#5a0a0a")))
    p.drawPath(path)
    p.setPen(QPen(QColor("#f85149"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    m=6; p.setPen(QPen(QColor("#f85149"),2))
    p.drawLine(cx-m+2,cy-m+4,cx+m-2,cy+m-2)
    p.drawLine(cx+m-2,cy-m+4,cx-m+2,cy+m-2)

def _draw_restore(p, r):
    p.fillRect(r, QColor("#3d0000"))
    p.setPen(QPen(QColor("#ff4444"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    arm,thick = 7,4
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#ff4444")))
    p.drawRect(cx-thick//2,cy-arm,thick,arm*2)
    p.drawRect(cx-arm,cy-thick//2,arm*2,thick)
    p.setPen(QPen(QColor("#ffaaaa"),1))
    f=QFont("monospace",6,QFont.Weight.Bold); p.setFont(f)
    p.drawText(QRect(cx+6,cy-10,10,10),Qt.AlignmentFlag.AlignCenter,"!")

def _draw_cache(p, r):
    p.fillRect(r, QColor("#1e1230"))
    p.setPen(QPen(QColor("#d2a8ff"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    bw,bh = 14,11; bx,by = cx-bw//2,cy-bh//2
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#2d1a4a")))
    p.drawRect(bx,by,bw,bh)
    p.setPen(QPen(QColor("#d2a8ff"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(bx,by,bw,bh)
    p.drawLine(bx,by+4,bx+bw,by+4)
    p.drawArc(cx-3,by-3,6,5,0,180*16)

def _draw_core(p, r):
    p.fillRect(r, QColor("#0a2510"))
    p.setPen(QPen(QColor("#3fb950"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    outer,inner = 11,5
    pts=[]
    for i in range(12):
        ang=math.radians(i*30-90); rad=outer if i%2==0 else inner
        pts.append(QPoint(int(cx+rad*math.cos(ang)),int(cy+rad*math.sin(ang))))
    poly=QPolygon(pts)
    g=QRadialGradient(cx,cy,outer)
    g.setColorAt(0,QColor("#7fff8a")); g.setColorAt(0.5,QColor("#3fb950")); g.setColorAt(1,QColor("#0a2510"))
    p.setPen(QPen(QColor("#3fb950"),1)); p.setBrush(QBrush(g))
    p.drawPolygon(poly)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#ccffcc")))
    p.drawEllipse(cx-2,cy-2,4,4)

def _draw_suppress(p, r):
    p.fillRect(r, QColor("#1f1a00"))
    p.setPen(QPen(QColor("#e3b341"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    pts=[QPoint(cx,cy+9),QPoint(cx-7,cy-1),QPoint(cx-3,cy-1),
         QPoint(cx-3,cy-9),QPoint(cx+3,cy-9),QPoint(cx+3,cy-1),QPoint(cx+7,cy-1)]
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#e3b341")))
    p.drawPolygon(QPolygon(pts))

def _draw_start(p, r):
    p.fillRect(r, QColor("#0d1f36"))
    p.setPen(QPen(QColor("#79c0ff"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r.adjusted(0,0,-1,-1))
    cx,cy = r.center().x(), r.center().y()
    pts=[QPoint(cx+9,cy),QPoint(cx-1,cy-7),QPoint(cx-1,cy-3),
         QPoint(cx-9,cy-3),QPoint(cx-9,cy+3),QPoint(cx-1,cy+3),QPoint(cx-1,cy+7)]
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#79c0ff")))
    p.drawPolygon(QPolygon(pts))

def _draw_for_type(p, r, ntype, value=0, heat=0.0):
    if   ntype == NODE_HIDDEN:    _draw_hidden(p, r, heat)
    elif ntype == NODE_EMPTY:     _draw_empty(p, r)
    elif ntype == NODE_NUM:       _draw_num(p, r, value)
    elif ntype == NODE_FIREWALL:  _draw_firewall(p, r)
    elif ntype == NODE_ANTIVIRUS: _draw_antivirus(p, r)
    elif ntype == NODE_RESTORE:   _draw_restore(p, r)
    elif ntype == NODE_CACHE:     _draw_cache(p, r)
    elif ntype == NODE_CORE:      _draw_core(p, r)
    elif ntype == NODE_SUPPRESS:  _draw_suppress(p, r)
    elif ntype == NODE_START:     _draw_start(p, r)
    else:                         _draw_hidden(p, r)


# ──────────────────────────────────────────────────────────────────────────────
# Miniatura da legenda
# ──────────────────────────────────────────────────────────────────────────────
class LegendCell(QWidget):
    def __init__(self, ntype, value=0, parent=None):
        super().__init__(parent)
        self.ntype=ntype; self.value=value; self.setFixedSize(26,26)
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        _draw_for_type(p,QRect(0,0,self.width(),self.height()),self.ntype,self.value)
        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# Nó do grafo
# ──────────────────────────────────────────────────────────────────────────────
class HackNode:
    _nid = 0
    def __init__(self, gx, gy, ntype=NODE_HIDDEN, value=0):
        self.id=HackNode._nid; HackNode._nid+=1
        self.gx=gx; self.gy=gy; self.type=ntype; self.value=value; self.heat=0.0


# ──────────────────────────────────────────────────────────────────────────────
# Canvas interativo — grafo relativo
# ──────────────────────────────────────────────────────────────────────────────
class HackCanvas(QWidget):
    expand_req    = pyqtSignal(int, int)   # (dgx, dgy)
    node_selected = pyqtSignal(object)     # HackNode

    STEP = 52   # pixels entre nós adjacentes
    HALF = 16   # metade do tamanho do ícone (ícone = 32×32)
    BTN  = 13   # raio do botão "+" de expansão

    DIRS = [(0,-1,"↑"),(1,0,"→"),(0,1,"↓"),(-1,0,"←")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        self.nodes    = {}          # (gx,gy) → HackNode
        self.selected = None
        self.pan_x    = 0
        self.pan_y    = 0
        self._hover   = None        # (dgx,dgy) hover sobre botão "+"

        self._add_node(0, 0, NODE_START)

    # ── helpers de posição ────────────────────────────────────────────────────
    def _cx(self): return self.width()//2  + self.pan_x
    def _cy(self): return self.height()//2 + self.pan_y
    def _px(self, gx): return self._cx() + gx*self.STEP
    def _py(self, gy): return self._cy() + gy*self.STEP

    def _expand_dirs(self):
        """Direções expansíveis a partir do nó selecionado."""
        if not self.selected: return []
        gx,gy = self.selected.gx, self.selected.gy
        return [(dgx,dgy,lbl,
                 self._px(gx+dgx), self._py(gy+dgy))
                for dgx,dgy,lbl in self.DIRS
                if (gx+dgx, gy+dgy) not in self.nodes]

    # ── grafo ─────────────────────────────────────────────────────────────────
    def _add_node(self, gx, gy, ntype, value=0):
        node = HackNode(gx, gy, ntype, value)
        self.nodes[(gx,gy)] = node
        self.selected = node
        self._center_on(node)
        self.refresh_heat()
        return node

    def delete_node(self, node):
        if node.gx==0 and node.gy==0: return   # não apaga a entrada
        del self.nodes[(node.gx, node.gy)]
        # Remove nós que ficaram desconectados da entrada
        reachable = set()
        stack = [(0,0)]
        while stack:
            pos = stack.pop()
            if pos in reachable or pos not in self.nodes: continue
            reachable.add(pos)
            gx,gy = pos
            for dgx,dgy,_ in self.DIRS:
                stack.append((gx+dgx, gy+dgy))
        for pos in list(self.nodes.keys()):
            if pos not in reachable:
                del self.nodes[pos]
        # Seleciona entrada
        self.selected = self.nodes.get((0,0))
        self.refresh_heat()

    def _center_on(self, node):
        self.pan_x = -(node.gx * self.STEP)
        self.pan_y = -(node.gy * self.STEP)

    # ── heat map ──────────────────────────────────────────────────────────────
    def _compute_heat(self):
        votes = {}
        for node in self.nodes.values():
            if node.type == NODE_NUM and node.value > 0:
                n = node.value
                for dx in range(-8,9):
                    for dy in range(-8,9):
                        if abs(dx)+abs(dy) == n:
                            pos = (node.gx+dx, node.gy+dy)
                            if pos not in self.nodes:
                                votes[pos] = votes.get(pos,0)+1
        if not votes: return {}
        mx = max(votes.values())
        return {pos:v/mx for pos,v in votes.items()}

    def refresh_heat(self):
        hm = self._compute_heat()
        for pos,node in self.nodes.items():
            node.heat = hm.get(pos, 0.0)
        self.update()

    # ── painter ───────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1117"))

        # grade de pontos (contexto visual leve)
        p.setPen(QPen(QColor("#1a1f27"),1))
        for gx in range(-7,8):
            for gy in range(-7,8):
                px,py = self._px(gx), self._py(gy)
                if 4<px<self.width()-4 and 4<py<self.height()-4:
                    p.drawPoint(px,py)

        # conexões entre nós conhecidos
        drawn = set()
        for (gx,gy) in self.nodes:
            for dgx,dgy,_ in self.DIRS:
                nb=(gx+dgx,gy+dgy)
                key=tuple(sorted([(gx,gy),nb]))
                if nb in self.nodes and key not in drawn:
                    drawn.add(key)
                    p.setPen(QPen(QColor("#2d3748"),2))
                    p.drawLine(self._px(gx),self._py(gy),self._px(nb[0]),self._py(nb[1]))

        hm = self._compute_heat()

        # botões "+" de expansão ao redor do nó selecionado
        HALF=self.HALF; BTN=self.BTN
        if self.selected:
            for dgx,dgy,lbl,bpx,bpy in self._expand_dirs():
                h = hm.get((self.selected.gx+dgx, self.selected.gy+dgy), 0.0)
                hov = self._hover == (dgx,dgy)
                # fundo do botão
                t=min(h,1.0)
                if t>0.05:
                    bg=QColor(int(25+t*175),int(25*(1-t)),int(25*(1-t)))
                else:
                    bg=QColor("#1c2128")
                if hov: bg=bg.lighter(150)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bg))
                p.drawRoundedRect(bpx-BTN,bpy-BTN,BTN*2,BTN*2,3,3)
                # borda
                bc = QColor("#ef4444") if t>0.6 else (QColor("#58a6ff") if hov else QColor("#30363d"))
                p.setPen(QPen(bc,2 if hov or t>0.6 else 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(bpx-BTN,bpy-BTN,BTN*2,BTN*2,3,3)
                # label
                icon = "⚡?" if t>0.85 else lbl
                p.setPen(QPen(QColor("#fca5a5") if t>0.6 else QColor("#6e7681"),1))
                f=QFont("monospace",10 if icon==lbl else 8,QFont.Weight.Bold)
                p.setFont(f)
                p.drawText(QRect(bpx-BTN,bpy-BTN,BTN*2,BTN*2),Qt.AlignmentFlag.AlignCenter,icon)
                # percentual de calor
                if t>0.3:
                    p.setPen(QPen(QColor("#fca5a5"),1))
                    f2=QFont("monospace",6); p.setFont(f2)
                    p.drawText(QRect(bpx-BTN,bpy+BTN,BTN*2,12),
                               Qt.AlignmentFlag.AlignCenter,f"{t:.0%}")

        # nós do grafo
        for (gx,gy),node in self.nodes.items():
            px,py=self._px(gx),self._py(gy)
            r=QRect(px-HALF,py-HALF,HALF*2,HALF*2)
            _draw_for_type(p,r,node.type,node.value,node.heat)
            # selecionado: borda azul
            if node==self.selected:
                p.setPen(QPen(QColor("#58a6ff"),2)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(-3,-3,3,3),5,5)

        p.end()

    # ── mouse ─────────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, e):
        if not self.selected: return
        mx,my=int(e.position().x()),int(e.position().y())
        BTN=self.BTN+3
        prev=self._hover; self._hover=None
        for dgx,dgy,_,bpx,bpy in self._expand_dirs():
            if abs(mx-bpx)<BTN and abs(my-bpy)<BTN:
                self._hover=(dgx,dgy); break
        if prev!=self._hover: self.update()

    def mousePressEvent(self, e):
        mx,my=int(e.position().x()),int(e.position().y())
        BTN=self.BTN+4; HALF=self.HALF+4

        if e.button()==Qt.MouseButton.LeftButton:
            # botão "+"
            for dgx,dgy,_,bpx,bpy in self._expand_dirs():
                if abs(mx-bpx)<BTN and abs(my-bpy)<BTN:
                    self.expand_req.emit(dgx,dgy); return
            # nó existente
            for node in self.nodes.values():
                nx,ny=self._px(node.gx),self._py(node.gy)
                if abs(mx-nx)<HALF and abs(my-ny)<HALF:
                    self.selected=node; self.node_selected.emit(node)
                    self.update(); return

        elif e.button()==Qt.MouseButton.RightButton:
            # apagar nó (clique direito)
            for node in self.nodes.values():
                nx,ny=self._px(node.gx),self._py(node.gy)
                if abs(mx-nx)<HALF and abs(my-ny)<HALF:
                    self.delete_node(node); self.update(); return


# ──────────────────────────────────────────────────────────────────────────────
# Bridge OCR
# ──────────────────────────────────────────────────────────────────────────────
class HackScanBridge(QObject):
    scan_completed = pyqtSignal(dict)
    scan_error     = pyqtSignal(str)


# ──────────────────────────────────────────────────────────────────────────────
# Widget Principal
# ──────────────────────────────────────────────────────────────────────────────
class HackingTabWidget(QWidget):
    def __init__(self, log_dir=None, parent=None):
        super().__init__(parent)
        self.log_dir             = log_dir
        self.current_target_name = "Survey Ship"
        self.coherence           = 70
        self.max_coherence       = 100
        self.strength            = 20
        self.sel_type            = NODE_NUM
        self.sel_value           = 3

        self.scan_bridge = HackScanBridge()
        self.scan_bridge.scan_completed.connect(self.on_scan_completed)
        self.scan_bridge.scan_error.connect(self.on_scan_error)

        self.init_ui()
        self.check_recent_logs_for_target()

    # ──────────────────────────────────────────────────────────────────────────
    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6,6,6,6)
        root.setSpacing(5)

        # ── Status bar ────────────────────────────────────────────────────────
        top = self._frame("#181b22","#30363d")
        tl  = QVBoxLayout(top); tl.setContentsMargins(6,4,6,4); tl.setSpacing(3)
        r1  = QHBoxLayout(); r1.setSpacing(6)
        self.btn_scan = self._mkbtn("📸 Escanear EVE","#388bfd",h=24)
        self.btn_scan.clicked.connect(self.handle_scan_screen)
        r1.addWidget(self.btn_scan)
        self.lbl_status = QLabel("Scanner pronto")
        self.lbl_status.setStyleSheet("color:#8b949e;font-size:10px;")
        r1.addWidget(self.lbl_status); r1.addStretch()
        self.lbl_target = QLabel(f"Alvo: {self.current_target_name}")
        self.lbl_target.setStyleSheet("color:#c9d1d9;font-size:10px;font-weight:bold;")
        r1.addWidget(self.lbl_target); tl.addLayout(r1)

        r2=QHBoxLayout(); r2.setSpacing(6)
        self.lbl_hp = QLabel(f"Coerência: {self.coherence}/{self.max_coherence}")
        self.lbl_hp.setStyleSheet("color:#58a6ff;font-size:10px;font-weight:bold;")
        r2.addWidget(self.lbl_hp)
        self.bar_hp = QProgressBar()
        self.bar_hp.setFixedHeight(7); self.bar_hp.setRange(0,self.max_coherence)
        self.bar_hp.setValue(self.coherence); self.bar_hp.setTextVisible(False)
        self.bar_hp.setStyleSheet("QProgressBar{background:#0d1117;border:1px solid #30363d;border-radius:2px;} QProgressBar::chunk{background:#2ea043;}")
        r2.addWidget(self.bar_hp,stretch=1)
        self.lbl_str = QLabel(f"Força: {self.strength}")
        self.lbl_str.setStyleSheet("color:#79c0ff;font-size:10px;font-weight:bold;")
        r2.addWidget(self.lbl_str); tl.addLayout(r2)
        root.addWidget(top)

        # ── Aviso Survey Ship ─────────────────────────────────────────────────
        self.frame_warning = self._frame("#261c10","#9e6a03")
        fw=QHBoxLayout(self.frame_warning); fw.setContentsMargins(6,2,6,2)
        self.lbl_warning=QLabel("⚠️  Survey Ship: use DATA ANALYZER, não Relic Analyzer!")
        self.lbl_warning.setStyleSheet("color:#e3b341;font-size:10px;")
        fw.addWidget(self.lbl_warning); root.addWidget(self.frame_warning)

        # ── Scroll ────────────────────────────────────────────────────────────
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;border:none;")
        cont=QWidget(); cl=QVBoxLayout(cont); cl.setContentsMargins(0,2,0,4); cl.setSpacing(5)

        # ── Legenda visual ────────────────────────────────────────────────────
        cl.addWidget(self._build_legend())

        # ── Paleta ────────────────────────────────────────────────────────────
        cl.addWidget(self._build_palette())

        # ── Canvas do grafo ───────────────────────────────────────────────────
        self.canvas = HackCanvas()
        self.canvas.expand_req.connect(self._on_expand)
        self.canvas.node_selected.connect(self._on_node_selected)
        cl.addWidget(self.canvas)

        # ── Botões de direção ─────────────────────────────────────────────────
        cl.addWidget(self._build_dir_buttons())

        # ── Conselho tático ───────────────────────────────────────────────────
        adv=self._frame("#0d1117","#30363d")
        al=QVBoxLayout(adv); al.setContentsMargins(8,6,8,6); al.setSpacing(2)
        self.lbl_adv_title=QLabel("AGUARDANDO — MARQUE O NÓ DE ENTRADA")
        self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#58a6ff;")
        al.addWidget(self.lbl_adv_title)
        self.lbl_adv_text=QLabel(
            "Selecione o tipo na paleta → clique numa seta do canvas para revelar o nó.\n"
            "O mapa de calor vai apontar onde o Core provavelmente está.")
        self.lbl_adv_text.setStyleSheet("font-size:10px;color:#c9d1d9;")
        self.lbl_adv_text.setWordWrap(True)
        al.addWidget(self.lbl_adv_text)
        cl.addWidget(adv)

        # ── Guia de defesas ───────────────────────────────────────────────────
        cl.addWidget(self._build_defense_guide())
        cl.addStretch()

        scroll.setWidget(cont)
        root.addWidget(scroll,stretch=1)

    # ──────────────────────────────────────────────────────────────────────────
    def _build_legend(self):
        f=self._frame("#161b22","#1f6feb")
        fl=QVBoxLayout(f); fl.setContentsMargins(8,5,8,5); fl.setSpacing(3)
        t=QLabel("📖  LEGENDA — O QUE CADA NÓ PARECE")
        t.setStyleSheet("font-size:10px;font-weight:bold;color:#79c0ff;")
        fl.addWidget(t)
        rows=[
            (NODE_NUM,     3, "#58a6ff", "Número (círculo azul)","Distância ao Core. MENOR número = mais perto!"),
            (NODE_START,   0, "#79c0ff", "Entrada (seta azul)",  "Onde o hack começa. Ponto fixo."),
            (NODE_EMPTY,   0, "#6e7681", "Vazio (ponto cinza)",  "Passagem livre, sem perigo"),
            (NODE_CORE,    0, "#3fb950", "⚡ Core (estrela verde)","OBJETIVO — destrua para vencer!"),
            (NODE_FIREWALL,0, "#d29922", "🧱 Firewall (tijolos)", "Muito HP — contorne se puder"),
            (NODE_ANTIVIRUS,0,"#f85149", "🛡 Antivírus (escudo)", "Escudo c/ X — mate se estiver no caminho"),
            (NODE_RESTORE, 0, "#ff4444", "🩸 Restauração (cruz)", "MATE PRIMEIRO! Cura tudo a cada turno"),
            (NODE_SUPPRESS,0, "#e3b341", "⬇ Supressor (seta↓)", "Reduz seu ataque — mate se estiver fraco"),
            (NODE_CACHE,   0, "#d2a8ff", "📦 Cache (caixinha)",  "50% monstro — só abra se bloqueado"),
        ]
        for ntype,val,color,name,desc in rows:
            row=QHBoxLayout(); row.setSpacing(6)
            row.addWidget(LegendCell(ntype,val))
            ln=QLabel(name); ln.setFixedWidth(130)
            ln.setStyleSheet(f"font-size:9px;font-weight:bold;color:{color};")
            row.addWidget(ln)
            ld=QLabel(desc); ld.setStyleSheet("font-size:9px;color:#8b949e;")
            ld.setWordWrap(True); row.addWidget(ld,stretch=1)
            fl.addLayout(row)
        return f

    def _build_palette(self):
        f=self._frame("#161b22","#30363d")
        fl=QVBoxLayout(f); fl.setContentsMargins(8,5,8,5); fl.setSpacing(4)
        lbl=QLabel("SELECIONE O QUE VOCÊ VIU  →  CLIQUE A SETA DA DIREÇÃO NO MAPA:")
        lbl.setStyleSheet("font-size:10px;font-weight:bold;color:#f0f6fc;")
        fl.addWidget(lbl)

        self.pal_btns={}

        # números 1-5
        r1=QHBoxLayout(); r1.setSpacing(4)
        l=QLabel("Número:"); l.setStyleSheet("font-size:9px;color:#8b949e;")
        r1.addWidget(l)
        for v in [1,2,3,4,5]:
            btn=QPushButton(str(v))
            btn.setFixedSize(30,28); btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("""
                QPushButton{background:#0d2543;color:#58a6ff;border:1px solid #1f4e8c;
                    border-radius:3px;font-size:12px;font-weight:bold;}
                QPushButton:checked{background:#1f6feb;color:#fff;border-color:#58a6ff;}
                QPushButton:hover{background:#1a3b6e;}
            """)
            btn.clicked.connect(lambda _,vv=v: self._sel_num(vv))
            self.pal_btns[f"num_{v}"]=btn; r1.addWidget(btn)
        r1.addStretch(); fl.addLayout(r1)

        # tipos especiais
        r2=QHBoxLayout(); r2.setSpacing(3)
        specials=[
            (NODE_START,    "▶ Entrada",  "#79c0ff"),
            (NODE_FIREWALL, "🧱 Firewall","#d29922"),
            (NODE_ANTIVIRUS,"🛡 Antivírus","#f85149"),
            (NODE_RESTORE,  "🩸 Restaur.", "#ff4444"),
            (NODE_CACHE,    "📦 Cache",   "#d2a8ff"),
            (NODE_CORE,     "⚡ Core!",   "#3fb950"),
            (NODE_SUPPRESS, "⬇ Supres.", "#e3b341"),
            (NODE_EMPTY,    "· Vazio",    "#6e7681"),
        ]
        for ntype,label,color in specials:
            btn=QPushButton(label)
            btn.setFixedHeight(22); btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton{{background:#161b22;color:{color};border:1px solid #30363d;
                    border-radius:3px;font-size:8.5px;font-weight:bold;padding:0 2px;}}
                QPushButton:checked{{border:1.5px solid {color};background:#0d1117;}}
                QPushButton:hover{{border-color:{color};}}
            """)
            btn.clicked.connect(lambda _,t=ntype: self._sel_type(t))
            self.pal_btns[f"type_{ntype}"]=btn; r2.addWidget(btn,stretch=1)
        fl.addLayout(r2)

        # hint + reset
        r3=QHBoxLayout(); r3.setSpacing(4)
        btn_rst=QPushButton("🔄 Novo Hack")
        btn_rst.setFixedHeight(22); btn_rst.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_rst.setStyleSheet("QPushButton{background:#21262d;color:#8b949e;border:1px solid #30363d;border-radius:3px;font-size:9.5px;font-weight:bold;} QPushButton:hover{color:#f0f6fc;border-color:#58a6ff;}")
        btn_rst.clicked.connect(self._reset_canvas)
        r3.addWidget(btn_rst)
        self.lbl_hint=QLabel("Selecione o tipo → clique a seta da direção no mapa")
        self.lbl_hint.setStyleSheet("font-size:9px;color:#6e7681;")
        r3.addWidget(self.lbl_hint,stretch=1)
        fl.addLayout(r3)

        self._sel_num(3)
        return f

    def _build_dir_buttons(self):
        """Cruz de setas alternativa para expandir sem precisar clicar no canvas."""
        f=self._frame("#161b22","#30363d")
        fl=QVBoxLayout(f); fl.setContentsMargins(8,5,8,5); fl.setSpacing(3)
        lbl=QLabel("OU USE OS BOTÕES DE DIREÇÃO:")
        lbl.setStyleSheet("font-size:9.5px;font-weight:bold;color:#c9d1d9;")
        fl.addWidget(lbl)

        cross=QGridLayout(); cross.setSpacing(4)
        dirs=[(0,-1,"↑",0,1),(1,0,"→",1,2),(0,1,"↓",2,1),(-1,0,"←",1,0)]
        for dgx,dgy,lbl_t,gr,gc in dirs:
            btn=QPushButton(lbl_t)
            btn.setFixedSize(38,28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("""
                QPushButton{background:#21262d;color:#c9d1d9;border:1px solid #30363d;
                    border-radius:3px;font-size:14px;font-weight:bold;}
                QPushButton:hover{background:#388bfd;color:#fff;border-color:#58a6ff;}
            """)
            btn.clicked.connect(lambda _,x=dgx,y=dgy: self._on_expand(x,y))
            cross.addWidget(btn,gr,gc,Qt.AlignmentFlag.AlignCenter)

        # label central
        lbl_sel=QLabel("SEL")
        lbl_sel.setFixedSize(38,28)
        lbl_sel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sel.setStyleSheet("color:#6e7681;font-size:8px;background:#161b22;border:1px solid #30363d;border-radius:3px;")
        cross.addWidget(lbl_sel,1,1,Qt.AlignmentFlag.AlignCenter)

        cross_w=QWidget(); cross_w.setLayout(cross)
        row=QHBoxLayout()
        row.addStretch(); row.addWidget(cross_w); row.addStretch()
        fl.addLayout(row)

        lbl_hint=QLabel("btn direito no nó do mapa = apagar")
        lbl_hint.setStyleSheet("font-size:8.5px;color:#6e7681;")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fl.addWidget(lbl_hint)
        return f

    def _build_defense_guide(self):
        f=self._frame("#161b22","#30363d")
        fl=QVBoxLayout(f); fl.setContentsMargins(8,5,8,5); fl.setSpacing(3)
        t=QLabel("PRIORIDADE AO ENCONTRAR DEFESAS:")
        t.setStyleSheet("font-size:10px;font-weight:bold;color:#f0f6fc;")
        fl.addWidget(t)
        items=[
            (NODE_RESTORE,   "🩸 Restauração",  "#ff4444","1ª PRIORIDADE","Cura outros a cada turno — elimine JÁ"),
            (NODE_SUPPRESS,  "⬇ Supressor",    "#e3b341","2ª — SE FRACO", "Reduz seu ataque — mate se enfraquecer"),
            (NODE_ANTIVIRUS, "🛡 Antivírus",    "#f85149","3ª — NO CAMINHO","Escudo c/ X — mate se bloquear rota"),
            (NODE_FIREWALL,  "🧱 Firewall",     "#d29922","4ª — DÁ VOLTA", "Muito HP — só ataque se não houver outro jeito"),
            (NODE_CACHE,     "📦 Cache",         "#d2a8ff","EVITE (50% mob)","Monstro metade das vezes — só se preso"),
        ]
        for ntype,name,color,tag,desc in items:
            row=QHBoxLayout(); row.setSpacing(5)
            mini=LegendCell(ntype); mini.setFixedSize(22,22); row.addWidget(mini)
            ln=QLabel(name); ln.setFixedWidth(90)
            ln.setStyleSheet(f"font-size:9.5px;font-weight:bold;color:{color};")
            row.addWidget(ln)
            lt=QLabel(tag); lt.setFixedWidth(90)
            lt.setStyleSheet("font-size:8.5px;font-weight:bold;color:#f0f6fc;background:#21262d;border-radius:2px;padding:1px 4px;")
            row.addWidget(lt)
            ld=QLabel(desc); ld.setStyleSheet("font-size:8.5px;color:#8b949e;")
            ld.setWordWrap(True); row.addWidget(ld,stretch=1)
            fl.addLayout(row)
        return f

    # ──────────────────────────────────────────────────────────────────────────
    # Paleta: seleção
    # ──────────────────────────────────────────────────────────────────────────
    def _clear_pal(self):
        for b in self.pal_btns.values(): b.setChecked(False)

    def _sel_num(self,v):
        self._clear_pal(); self.sel_type=NODE_NUM; self.sel_value=v
        self.pal_btns[f"num_{v}"].setChecked(True)
        self.lbl_hint.setText(f"Vai revelar um nó → clique a seta da direção (colocará o número {v})")

    def _sel_type(self,ntype):
        self._clear_pal(); self.sel_type=ntype; self.sel_value=0
        key=f"type_{ntype}"
        if key in self.pal_btns: self.pal_btns[key].setChecked(True)
        msgs={
            NODE_START:    "Clique a seta para marcar o ponto de ENTRADA",
            NODE_FIREWALL: "Clique a seta onde você viu a PAREDE DE TIJOLOS (Firewall)",
            NODE_ANTIVIRUS:"Clique a seta onde você viu o ESCUDO COM X (Antivírus)",
            NODE_RESTORE:  "⚠ Restauração! Clique a seta — vá matar esse nó AGORA",
            NODE_CACHE:    "Clique a seta onde apareceu a CAIXINHA (Cache)",
            NODE_CORE:     "Clique a seta onde você viu a ESTRELA VERDE — você achou o Core!",
            NODE_SUPPRESS: "Clique a seta onde apareceu a SETA PARA BAIXO (Supressor)",
            NODE_EMPTY:    "Clique a seta onde o nó estava vazio",
        }
        self.lbl_hint.setText(msgs.get(ntype,"Clique a seta de direção no mapa"))

    # ──────────────────────────────────────────────────────────────────────────
    # Ações no canvas
    # ──────────────────────────────────────────────────────────────────────────
    def _on_expand(self, dgx, dgy):
        if not self.canvas.selected: return
        sel=self.canvas.selected
        new_pos=(sel.gx+dgx, sel.gy+dgy)
        if new_pos in self.canvas.nodes:
            # Nó já existe: apenas muda tipo
            n=self.canvas.nodes[new_pos]
            n.type=self.sel_type; n.value=self.sel_value
            self.canvas.selected=n
        else:
            self.canvas._add_node(sel.gx+dgx, sel.gy+dgy, self.sel_type, self.sel_value)
        self.canvas.refresh_heat()
        self._update_advice()

    def _on_node_selected(self, node):
        self._update_advice()

    def _reset_canvas(self):
        HackNode._nid=0
        self.canvas.nodes={}
        self.canvas.pan_x=0; self.canvas.pan_y=0
        self.canvas._add_node(0,0,NODE_START)
        self.canvas.update()
        self.lbl_adv_title.setText("NOVO HACK — MARQUE O PONTO DE ENTRADA")
        self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#58a6ff;")
        self.lbl_adv_text.setText("Selecione o tipo na paleta → clique a seta da direção para revelar.")

    # ──────────────────────────────────────────────────────────────────────────
    # Conselho tático
    # ──────────────────────────────────────────────────────────────────────────
    def _update_advice(self):
        nodes=self.canvas.nodes

        # Core encontrado?
        for node in nodes.values():
            if node.type==NODE_CORE:
                self.lbl_adv_title.setText("⚡ CORE ENCONTRADO — DESTRUA!")
                self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#3fb950;")
                self.lbl_adv_text.setText(
                    "Clique no Core (estrela verde) repetidamente até destruir.\n"
                    "Se houver Restauração (🩸) ativa, elimine-a ANTES de focar no Core.")
                return

        # Restauração ativa?
        for node in nodes.values():
            if node.type==NODE_RESTORE:
                self.lbl_adv_title.setText("🩸 RESTAURAÇÃO — MATE JÁ!")
                self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#ff4444;")
                self.lbl_adv_text.setText(
                    "Nó de Restauração (cruz vermelha) está curando as defesas a cada turno.\n"
                    "PRIORIDADE MÁXIMA: destrua-o antes de qualquer outro clique.")
                return

        num_nodes=[(n.gx,n.gy,n.value) for n in nodes.values()
                   if n.type==NODE_NUM and n.value>0]

        if not num_nodes:
            self.lbl_adv_title.setText("AGUARDANDO DADOS")
            self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#58a6ff;")
            self.lbl_adv_text.setText(
                "Selecione o tipo na paleta e clique as setas para revelar nós.\n"
                "Conforme marcar os números, o mapa de calor vai convergir para o Core.")
            return

        hm=self.canvas._compute_heat()
        best=max(hm, key=hm.get) if hm else None
        best_h=hm[best] if best else 0.0
        min_n=min(num_nodes,key=lambda x:x[2])

        if min_n[2]==1:
            self.lbl_adv_title.setText("DISTÂNCIA 1 — CORE COLADO AQUI!")
            self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#e3b341;")
            self.lbl_adv_text.setText(
                "Um nó marcado com '1' significa que o Core está em alguma seta ADJACENTE a ele.\n"
                "Selecione o nó '1' no mapa → revele as setas ao redor para achar o Core.")
        elif best and best_h>=0.5:
            self.lbl_adv_title.setText(f"CORE PROVÁVEL  ({best_h:.0%} de certeza)")
            self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#7ee787;")
            self.lbl_adv_text.setText(
                f"Os números convergem para uma posição com {best_h:.0%} de certeza.\n"
                f"Avance na seta mais VERMELHA/QUENTE do mapa — ela aponta para o Core.\n"
                f"Menor número revelado: {min_n[2]} — Core ainda a {min_n[2]} salto(s).")
        else:
            self.lbl_adv_title.setText(f"ANALISANDO — menor número: {min_n[2]}")
            self.lbl_adv_title.setStyleSheet("font-size:11px;font-weight:bold;color:#58a6ff;")
            self.lbl_adv_text.setText(
                f"Menor número revelado: {min_n[2]}.\n"
                "Continue revelando nós na direção onde o número DIMINUI.\n"
                "O calor vermelho vai ficar mais intenso conforme se aproxima do Core.")

    # ──────────────────────────────────────────────────────────────────────────
    # OCR / scan
    # ──────────────────────────────────────────────────────────────────────────
    def handle_scan_screen(self):
        self.btn_scan.setEnabled(False); self.btn_scan.setText("Escaneando...")
        self.lbl_status.setText("Capturando tela...")
        self.lbl_status.setStyleSheet("color:#e3b341;font-size:10px;")
        def worker():
            tmp="/tmp/eve_hack_scan.png"
            try:
                subprocess.run(["spectacle","-b","-n","-f","-o",tmp],
                               capture_output=True,text=True,timeout=4)
                if not os.path.exists(tmp):
                    self.scan_bridge.scan_error.emit("Erro na captura."); return
                img=Image.open(tmp); w,h=img.size
                crop=img.crop((int(w*.15),int(h*.15),int(w*.85),int(h*.85)))
                cp="/tmp/eve_hack_crop.png"; crop.save(cp)
                res=subprocess.run(["tesseract",cp,"stdout","--psm","6"],
                                   capture_output=True,text=True)
                ocr=res.stdout or ""
                is_hack=any(k in ocr.lower() for k in ["empty node","connector","encrypted","coherence"])
                cw,ch=crop.size
                sc=crop.crop((40,ch-160,260,ch)).convert("L")
                sc=sc.resize((sc.width*4,sc.height*4),Image.Resampling.LANCZOS)
                th=sc.point(lambda px:255 if px>150 else 0)
                tp="/tmp/eve_hack_status.png"; th.save(tp)
                res2=subprocess.run(["tesseract",tp,"stdout","--psm","11"],
                                    capture_output=True,text=True)
                st=res2.stdout or ""
                coh,stg=70,20
                digs=re.findall(r"\b(\d{2,3})\b",st)
                if digs:
                    coh=int(digs[0])
                    if len(digs)>1: stg=int(digs[-1])
                self.scan_bridge.scan_completed.emit({"is_hack":is_hack,"coherence":coh,"strength":stg})
            except Exception as ex:
                self.scan_bridge.scan_error.emit(str(ex))
        threading.Thread(target=worker,daemon=True).start()

    def on_scan_completed(self,data):
        self.btn_scan.setEnabled(True); self.btn_scan.setText("📸 Escanear EVE")
        self.coherence=data.get("coherence",70); self.strength=data.get("strength",20)
        self.lbl_hp.setText(f"Coerência: {self.coherence}/{self.max_coherence}")
        self.bar_hp.setValue(self.coherence); self.lbl_str.setText(f"Força: {self.strength}")
        st="🟢 Hack detectado" if data.get("is_hack") else "Aguardando hack"
        col="#7ee787" if data.get("is_hack") else "#8b949e"
        self.lbl_status.setText(st); self.lbl_status.setStyleSheet(f"color:{col};font-size:10px;")
        self.check_recent_logs_for_target()

    def on_scan_error(self,_):
        self.btn_scan.setEnabled(True); self.btn_scan.setText("📸 Escanear EVE")
        self.lbl_status.setText("Erro na captura")
        self.lbl_status.setStyleSheet("color:#ff7b72;font-size:10px;")

    def check_recent_logs_for_target(self):
        if not self.log_dir or not os.path.exists(self.log_dir): return
        files=glob.glob(os.path.join(self.log_dir,"*.txt"))
        if not files: return
        latest=max(files,key=os.path.getmtime)
        try:
            with open(latest,"r",encoding="utf-8",errors="ignore") as f:
                content="".join(f.readlines()[-30:])
            survey=("cannot access the Survey Ship" in content
                    or "survey" in self.current_target_name.lower())
            self.frame_warning.setVisible(survey)
        except Exception: pass

    def auto_configure(self,log_dir=None,target_name=None,system_security=None):
        if log_dir is not None: self.log_dir=log_dir
        if target_name is not None: self.current_target_name=target_name
        self.lbl_target.setText(f"Alvo: {self.current_target_name}")
        self.check_recent_logs_for_target()

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────
    def _frame(self,bg,border):
        f=QFrame()
        f.setStyleSheet(f"background:{bg};border:1px solid {border};border-radius:4px;")
        return f

    def _mkbtn(self,text,border,h=26):
        b=QPushButton(text); b.setFixedHeight(h)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(f"""
            QPushButton{{background:#21262d;color:#f0f6fc;border:1px solid {border};
                border-radius:3px;font-size:10px;font-weight:bold;padding:0 8px;}}
            QPushButton:hover{{background:{border};color:#fff;}}
            QPushButton:disabled{{opacity:0.5;}}
        """)
        return b
