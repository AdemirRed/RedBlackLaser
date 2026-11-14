"""Render da prévia do copo gravado no Blender (Cycles, placa de vídeo: OptiX/CUDA/HIP; sem GPU usa o processador).

O RedBlack não leva o Blender junto: usa o que estiver instalado (procura nas pastas de sempre ou no caminho salvo).
O script da cena vai embutido aqui (no .exe não existem arquivos .py soltos) e é gravado numa pasta temporária."""
import glob
import json
import os
import shutil

from . import calc
from .vista3d import raio_rotativo

# acabamento por material: corpo (metálico, rugosidade, vidro, verniz) · gravação (metálico, rugosidade)
MATERIAIS_RENDER = {
    "Copo pintado / térmico (gravação revela o inox)": (0.0, 0.55, False, 0.35, 1.0, 0.38),
    "Inox sem pintura (gravação escurece)": (1.0, 0.24, False, 0.0, 0.85, 0.55),
    "Alumínio anodizado (gravação fica clara)": (0.85, 0.35, False, 0.0, 0.9, 0.45),
    "Madeira / bambu (gravação queimada)": (0.0, 0.6, False, 0.1, 0.0, 0.9),
    "Couro (gravação queimada)": (0.0, 0.7, False, 0.0, 0.0, 0.85),
    "Vidro / cristal (gravação jateada)": (0.0, 0.02, True, 0.0, 0.0, 0.85),
}


def linear(cor_hex):
    """#rrggbb (sRGB) -> cor linear do Blender."""
    from PySide6.QtGui import QColor
    c = QColor(cor_hex)

    def lin(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return [lin(c.redF()), lin(c.greenF()), lin(c.blueF())]


def localizar_blender(salvo=""):
    """Caminho do blender.exe (o salvo, se existir; senão o mais novo encontrado) ou ''."""
    if salvo and os.path.isfile(salvo):
        return salvo
    achados = []
    for raiz in ("C:\\Program Files\\Blender Foundation", "D:\\Blender Foundation", "E:\\Blender Foundation",
                 "F:\\Blender Foundation", "C:\\Program Files (x86)\\Steam\\steamapps\\common",
                 os.path.expandvars("%LOCALAPPDATA%\\Programs\\Blender Foundation")):
        achados += glob.glob(os.path.join(raiz, "Blender*", "blender.exe"))
    achados.sort(key=lambda c: os.path.getmtime(c), reverse=True)
    if achados:
        return achados[0]
    return shutil.which("blender") or ""


def preparar(pasta, p: calc.Peca, angulo_arte, arte, material, yaw, pitch, resolucao=1400, amostras=160,
             cor_corpo="#1d1e21", cor_arte="#b4b8be"):
    """Grava textura + dados da cena em `pasta`. Devolve (script, dados, saída)."""
    os.makedirs(pasta, exist_ok=True)
    n = 160
    perfil = [(p.altura * i / n, calc.diametro_em(p, p.altura * i / n) / 2) for i in range(n + 1)]
    dados = {"perfil": perfil, "altura": p.altura, "inicio": p.inicio, "r_ref": raio_rotativo(p),
             "angulo": angulo_arte, "yaw": yaw, "pitch": pitch, "material": MATERIAIS_RENDER[material],
             "cor_corpo": linear(cor_corpo), "cor_arte": linear(cor_arte),
             "resolucao": resolucao, "amostras": amostras, "arte": None,
             "saida": os.path.join(pasta, "previa_copo.png")}
    if arte is not None:
        img, w_mm, h_mm = arte
        tex = os.path.join(pasta, "arte.png")
        img.save(tex, "PNG")
        dados["arte"] = {"arquivo": tex, "w": w_mm, "h": h_mm}
    caminho_dados = os.path.join(pasta, "cena.json")
    with open(caminho_dados, "w", encoding="utf-8") as f:
        json.dump(dados, f)
    script = os.path.join(pasta, "cena_copo.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(SCRIPT)
    return script, caminho_dados, dados["saida"]


def argumentos(script, dados):
    return ["-b", "--factory-startup", "-P", script, "--", dados]


SCRIPT = r'''
import json, math, sys
import bpy, bmesh

d = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
MM = 0.001
bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene
perfil, H = d["perfil"], d["altura"]
N = 192
phi = math.radians(d["angulo"])
esp = 1.6  # parede (mm)

bm = bmesh.new()
uvl = bm.loops.layers.uv.new("UV")
def anel(r, z):
    return [bm.verts.new(((r) * math.sin(phi - math.pi + 2 * math.pi * j / N) * MM,
                          -(r) * math.cos(phi - math.pi + 2 * math.pi * j / N) * MM, -z * MM)) for j in range(N + 1)]
fora = [anel(r, z) for z, r in perfil]
dentro = [anel(max(r - esp, 0.5), z) for z, r in perfil if z <= H - esp] or [anel(max(perfil[0][1] - esp, .5), 0)]
arte = d["arte"]
def uv(t, z):
    if not arte:
        return (-1.0, -1.0)
    return (d["r_ref"] * t / arte["w"] + 0.5, 1.0 - (z - d["inicio"]) / arte["h"])
faces_arte = []
for i in range(len(fora) - 1):
    for j in range(N):
        f = bm.faces.new((fora[i][j], fora[i + 1][j], fora[i + 1][j + 1], fora[i][j + 1]))
        zs = (perfil[i][0], perfil[i + 1][0], perfil[i + 1][0], perfil[i][0])
        ts = [-math.pi + 2 * math.pi * k / N for k in (j, j, j + 1, j + 1)]
        for lo, t, z in zip(f.loops, ts, zs):
            lo[uvl].uv = uv(t, z)
for i in range(len(dentro) - 1):
    for j in range(N):
        bm.faces.new((dentro[i][j + 1], dentro[i + 1][j + 1], dentro[i + 1][j], dentro[i][j]))
for j in range(N):  # borda da boca
    bm.faces.new((fora[0][j + 1], dentro[0][j + 1], dentro[0][j], fora[0][j]))
fundo_ext = bm.faces.new(list(reversed(fora[-1][:N])))
fundo_int = bm.faces.new(dentro[-1][:N])
bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts], dist=1e-7)
me = bpy.data.meshes.new("Copo")
bm.to_mesh(me)
bm.free()
for poly in me.polygons:
    poly.use_smooth = True
copo = bpy.data.objects.new("Copo", me)
cena.collection.objects.link(copo)

metal, rug, vidro, verniz, metal_a, rug_a = d["material"]
cor, cor_a = d["cor_corpo"], d["cor_arte"]
m = bpy.data.materials.new("Copo")
m.use_nodes = True
nt = m.node_tree
out = nt.nodes["Material Output"]
corpo = nt.nodes["Principled BSDF"]
corpo.inputs["Base Color"].default_value = (*cor, 1)
corpo.inputs["Metallic"].default_value = metal
corpo.inputs["Roughness"].default_value = rug
if verniz and "Coat Weight" in corpo.inputs:  # pintura eletrostática/epóxi: verniz por cima
    corpo.inputs["Coat Weight"].default_value = verniz
    corpo.inputs["Coat Roughness"].default_value = 0.25
if vidro:
    for nome in ("Transmission Weight", "Transmission"):
        if nome in corpo.inputs:
            corpo.inputs[nome].default_value = 1.0
            break
    corpo.inputs["IOR"].default_value = 1.5
if arte:
    gr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    gr.inputs["Base Color"].default_value = (*cor_a, 1)
    gr.inputs["Metallic"].default_value = metal_a
    gr.inputs["Roughness"].default_value = rug_a
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(arte["arquivo"])
    tex.extension = "CLIP"
    coord = nt.nodes.new("ShaderNodeUVMap")
    coord.uv_map = "UV"
    nt.links.new(coord.outputs["UV"], tex.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(corpo.outputs["BSDF"], mix.inputs[1])
    nt.links.new(gr.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
copo.data.materials.append(m)

# estúdio: mesa escura fosca, fundo infinito, softboxes grandes (o metal precisa de algo claro para refletir)
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -H * MM))
mesa = bpy.context.object
mt = bpy.data.materials.new("Mesa"); mt.use_nodes = True
b = mt.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.05, 0.045, 0.04, 1); b.inputs["Roughness"].default_value = 0.35
mesa.data.materials.append(mt)
GIRO = -math.radians(d["yaw"])  # luzes e fundo giram junto com a câmera: o lado visto fica sempre iluminado
def girar(x, y):
    return x * math.cos(GIRO) - y * math.sin(GIRO), x * math.sin(GIRO) + y * math.cos(GIRO)
bpy.ops.mesh.primitive_plane_add(size=4, location=(*girar(0, 0.6), -H * MM + 1.0),
                                 rotation=(math.radians(90), 0, GIRO))
fundo = bpy.context.object
mf = bpy.data.materials.new("Fundo"); mf.use_nodes = True
mf.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.095, 0.105, 1)
mf.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
fundo.data.materials.append(mf)
w = bpy.data.worlds.new("Mundo"); cena.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.2, 0.21, 0.23, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.12
alvo = bpy.data.objects.new("Alvo", None); alvo.location = (0, 0, -H * MM * 0.5); cena.collection.objects.link(alvo)
R = max(r for _, r in perfil) * MM
def luz(nome, loc, e, tam, forma="RECTANGLE", tam_y=None):
    l = bpy.data.lights.new(nome, "AREA"); l.energy = e; l.shape = forma; l.size = tam; l.size_y = tam_y or tam
    o = bpy.data.objects.new(nome, l); o.location = (*girar(loc[0], loc[1]), loc[2]); cena.collection.objects.link(o)
    c = o.constraints.new("TRACK_TO"); c.target = alvo
luz("Softbox esquerda", (-0.45, -0.25, 0.05), 14, 0.25, "RECTANGLE", 0.9)  # faixa vertical: reflexo longo no copo
luz("Softbox direita", (0.45, -0.2, 0.0), 7, 0.25, "RECTANGLE", 0.9)
luz("Topo", (0.0, -0.1, 0.55), 6, 0.6)
luz("Recorte", (0.15, 0.45, 0.25), 10, 0.3)
yaw, pitch = math.radians(d["yaw"]), math.radians(d["pitch"])
dist = max(H * MM, 2 * R) * 2.6
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 70
cam = bpy.data.objects.new("Cam", cam_d); cena.collection.objects.link(cam)
cam.location = (-dist * math.cos(pitch) * math.sin(yaw), -dist * math.cos(pitch) * math.cos(yaw),
                -H * MM * 0.5 + dist * math.sin(pitch))
c = cam.constraints.new("TRACK_TO"); c.target = alvo
cena.camera = cam

cena.render.engine = "CYCLES"
cena.cycles.samples = d["amostras"]
cena.cycles.use_denoising = True
cena.render.resolution_x = cena.render.resolution_y = d["resolucao"]
cena.render.filepath = d["saida"]
cena.render.image_settings.file_format = "PNG"
vts = [v.identifier for v in cena.view_settings.bl_rna.properties["view_transform"].enum_items]
cena.view_settings.view_transform = "AgX" if "AgX" in vts else "Filmic"
cena.view_settings.exposure = 0.0
looks = [v.identifier for v in cena.view_settings.bl_rna.properties["look"].enum_items]
cena.view_settings.look = next((x for x in looks if "Medium High" in x or "Punchy" in x), "None")
try:
    pref = bpy.context.preferences.addons["cycles"].preferences
    for tipo in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            pref.compute_device_type = tipo
            pref.get_devices()
            if any(x.type == tipo for x in pref.devices):
                for x in pref.devices:
                    x.use = True
                cena.cycles.device = "GPU"
                print("PLACA DE VIDEO:", tipo)
                break
        except TypeError:
            continue
except Exception as e:
    print("SEM GPU:", e)
bpy.ops.render.render(write_still=True)
print("RENDER OK", d["saida"])
'''
