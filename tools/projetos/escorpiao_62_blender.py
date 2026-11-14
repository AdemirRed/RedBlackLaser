"""Render 3D do Escorpião 62 montado, em cima de uma mesa (Blender 4.x/5.x, Cycles).

Executar:  blender -b -P tools/projetos/escorpiao_62_blender.py -- geometria.json saida.png [saida.blend]
A geometria vem de escorpiao_62.py (mesmo sistema do corpo: X para a direita, Y para baixo, mm).
Montagem: ombros dos pés no topo da base; base avança 12 mm para cada lado; corpo centrado nos rasgos; apliques
colados na face da frente (6 mm cada).
"""
import json
import math
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
geo = json.load(open(args[0], encoding="utf-8"))
SAIDA = args[1]
MM = 0.001
T = 6.0

bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene


# ---------- materiais ----------
def material(nome, cor, rug=0.6, borda=None, madeira=False):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rug
    cor_no = None
    if madeira:  # fibras do MDF / tampo: ruído alongado
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = madeira
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 6.0
        nz.inputs["Detail"].default_value = 8.0
        rp = nt.nodes.new("ShaderNodeValToRGB")
        rp.color_ramp.elements[0].color = [c * 0.82 for c in cor[:3]] + [1]
        rp.color_ramp.elements[1].color = list(cor[:3]) + [1]
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
        nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"])
        cor_no = rp.outputs["Color"]
    else:
        bsdf.inputs["Base Color"].default_value = cor
    if borda is not None:  # borda queimada do corte a laser: faces laterais (normal sem componente Y)
        geo_no = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(geo_no.outputs["Normal"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["Y"], ab.inputs[0])
        nt.links.new(ab.outputs[0], mix.inputs["Factor"])
        mix.inputs["A"].default_value = borda
        if cor_no is not None:
            nt.links.new(cor_no, mix.inputs["B"])
        else:
            mix.inputs["B"].default_value = cor
        cor_no = mix.outputs["Result"]
    if cor_no is not None:
        nt.links.new(cor_no, bsdf.inputs["Base Color"])
    return m


PRETO = material("Preto fosco", (0.008, 0.008, 0.009, 1), rug=0.85)
NATURAL = material("MDF natural", (0.55, 0.3, 0.13, 1), rug=0.7, borda=(0.09, 0.05, 0.03, 1), madeira=(40, 4, 40))
GRAFITE = material("Grafite", (0.05, 0.048, 0.046, 1), rug=0.55)
TAMPO = material("Tampo de madeira", (0.2, 0.09, 0.035, 1), rug=0.45, madeira=(3, 0.3, 3))
PAREDE = material("Parede", (0.45, 0.43, 0.4, 1), rug=0.9)


# ---------- peças: polígonos 2D -> chapa de 6 mm ----------
def chapa(nome, polis, mat, chanfro=0.25):
    cu = bpy.data.curves.new(nome, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = T / 2 * MM
    cu.bevel_depth = chanfro * MM
    cu.bevel_resolution = 2
    for pol in polis:
        if len(pol) > 1 and pol[0] == pol[-1]:
            pol = pol[:-1]
        sp = cu.splines.new("POLY")
        sp.points.add(len(pol) - 1)
        for p, (x, y) in zip(sp.points, pol):
            p.co = (x * MM, -y * MM, 0, 1)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(nome, cu)
    cena.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


# corpo em pé (face no plano XZ): z = 6 + (190 − y) mm; espessura no eixo Y centrada em 0
corpo = chapa("P01 Corpo", geo["corpo"], PRETO)
corpo.rotation_euler = (math.radians(90), 0, 0)
corpo.location = (0, 0, (T + 190) * MM)
for a in geo["apliques"]:
    o = chapa(f"{a['cod']} {a['nome']}", a["polis"], NATURAL if a["cor"] == "natural" else GRAFITE)
    o.rotation_euler = (math.radians(90), 0, 0)
    o.location = (0, -T * MM, (T + 190) * MM)  # colado na frente do corpo
base = chapa("P02 Base", geo["base"], PRETO, chanfro=0.4)
base.location = (-12 * MM, 34 * MM, T / 2 * MM)  # rasgos (Y 34 da base) no eixo do corpo

# ---------- mesa, parede, luz e câmera ----------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.11, 0.05, -0.0125))
mesa = bpy.context.object
mesa.scale = (1.6, 0.9, 0.025)
mesa.data.materials.append(TAMPO)
bev = mesa.modifiers.new("chanfro", "BEVEL")
bev.width = 0.003
bev.segments = 3
bpy.ops.mesh.primitive_plane_add(size=1, location=(0.11, 0.45, 0.4), rotation=(math.radians(90), 0, 0))
parede = bpy.context.object
parede.scale = (3, 1.2, 1)
parede.data.materials.append(PAREDE)

w = bpy.data.worlds.new("Mundo")
cena.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.57, 0.6, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.12


def luz(nome, loc, energia, tam, cor=(1, 1, 1)):
    d = bpy.data.lights.new(nome, "AREA")
    d.energy = energia
    d.size = tam
    d.color = cor
    o = bpy.data.objects.new(nome, d)
    o.location = loc
    cena.collection.objects.link(o)
    alvo = o.constraints.new("TRACK_TO")
    alvo.target = corpo
    return o


luz("Principal", (-0.35, -0.45, 0.55), 14, 0.5, (1.0, 0.95, 0.88))
luz("Preenchimento", (0.6, -0.4, 0.25), 4, 0.6, (0.85, 0.9, 1.0))
luz("Recorte", (0.25, 0.3, 0.5), 8, 0.3)

alvo = bpy.data.objects.new("Alvo", None)
alvo.location = (0.115, 0, 0.095)
cena.collection.objects.link(alvo)
cam_d = bpy.data.cameras.new("Camera")
cam_d.lens = 60
cam_d.dof.use_dof = True
cam_d.dof.focus_object = alvo
cam_d.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new("Camera", cam_d)
cam.location = (-0.12, -0.62, 0.24)
cena.collection.objects.link(cam)
tr = cam.constraints.new("TRACK_TO")
tr.target = alvo
cena.camera = cam

# ---------- render ----------
cena.render.engine = "CYCLES"
cena.cycles.samples = 160
cena.cycles.use_denoising = True
cena.render.resolution_x, cena.render.resolution_y = 1920, 1350
transformes = [v.identifier for v in cena.view_settings.bl_rna.properties["view_transform"].enum_items]
cena.view_settings.view_transform = "AgX" if "AgX" in transformes else "Filmic"
looks = [v.identifier for v in cena.view_settings.bl_rna.properties["look"].enum_items]
cena.view_settings.exposure = -1.0
cena.view_settings.look = next((x for x in looks if "Punchy" in x or "Medium High" in x), "None")
cena.render.filepath = SAIDA
cena.render.image_settings.file_format = "PNG"
try:  # GPU se houver
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for tipo in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = tipo
            prefs.get_devices()
            if any(d.type == tipo for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                cena.cycles.device = "GPU"
                print("GPU:", tipo)
                break
        except TypeError:
            continue
except Exception as e:  # noqa: BLE001
    print("CPU:", e)
if len(args) > 2:
    bpy.ops.wm.save_as_mainfile(filepath=args[2])
bpy.ops.render.render(write_still=True)
print("RENDER OK", SAIDA)
