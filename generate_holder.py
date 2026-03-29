from pathlib import Path
import trimesh
from trimesh.creation import box

# Kenwood TH-D75 desk holder, back-down cradle.
# Dimensions based on published radio body size: 56.0 x 121.95 x 32.5 mm.
# This script regenerates STL / OBJ / 3MF outputs.

def build_holder():
    radio_w = 56.0
    radio_h = 121.95
    clear = 1.2
    pocket_w = radio_w + 2*clear
    pocket_h = radio_h + 2*clear
    base_margin_x = 18.0
    base_margin_y = 20.0
    base_t = 6.0
    wall_h = 18.0
    wall_t = 6.0
    meshes = []

    base_w = pocket_w + 2*base_margin_x
    base_h = pocket_h + 2*base_margin_y

    base = box(extents=[base_w, base_h, base_t])
    base.apply_translation([0, 0, base_t/2])
    meshes.append(base)

    left_x = -(pocket_w/2 + wall_t/2)
    left = box(extents=[wall_t, pocket_h + 2*wall_t, wall_h])
    left.apply_translation([left_x, 0, base_t + wall_h/2])
    meshes.append(left)

    top_y = pocket_h/2 + wall_t/2
    notch_w = 28.0
    section_len = (pocket_w - notch_w)/2
    for sign in (-1, 1):
        top_seg = box(extents=[section_len, wall_t, wall_h])
        x = sign*(notch_w/2 + section_len/2)
        top_seg.apply_translation([x, top_y, base_t + wall_h/2])
        meshes.append(top_seg)

    bottom_y = -(pocket_h/2 + wall_t/2)
    front_seg_w = (pocket_w - 24.0)/2
    for sign in (-1, 1):
        bot_seg = box(extents=[front_seg_w, wall_t, wall_h])
        x = sign*((24.0/2) + front_seg_w/2)
        bot_seg.apply_translation([x, bottom_y, base_t + wall_h/2])
        meshes.append(bot_seg)

    right_x = (pocket_w/2 + wall_t/2)
    post_len = 22.0
    for y in (pocket_h/2 - post_len/2 + 4.0, -(pocket_h/2 - post_len/2 + 4.0)):
        post = box(extents=[wall_t, post_len, wall_h])
        post.apply_translation([right_x, y, base_t + wall_h/2])
        meshes.append(post)

    rail_h = 3.0
    rail_t = 2.2
    inner_left = box(extents=[rail_t, pocket_h-14.0, rail_h])
    inner_left.apply_translation([-(pocket_w/2) + rail_t/2, 0, base_t + rail_h/2])
    meshes.append(inner_left)
    for y in ((pocket_h/2) - rail_t/2, -((pocket_h/2) - rail_t/2)):
        seg = box(extents=[18.0, rail_t, rail_h])
        seg.apply_translation([-(pocket_w/2)+16.0, y, base_t + rail_h/2])
        meshes.append(seg)
        seg2 = box(extents=[18.0, rail_t, rail_h])
        seg2.apply_translation([(pocket_w/2)-16.0, y, base_t + rail_h/2])
        meshes.append(seg2)

    for x, y in [(base_w/2-12, base_h/2-12), (-base_w/2+12, base_h/2-12), (base_w/2-12, -base_h/2+12), (-base_w/2+12, -base_h/2+12)]:
        foot = box(extents=[12, 12, 2])
        foot.apply_translation([x, y, 1])
        meshes.append(foot)

    mesh = trimesh.util.concatenate(meshes)
    mesh.metadata['units'] = 'mm'
    return mesh

if __name__ == '__main__':
    out = Path('.')
    mesh = build_holder()
    mesh.export(out / 'th-d75-desk-holder-v2.stl')
    mesh.export(out / 'th-d75-desk-holder-v2.obj')
    mesh.export(out / 'th-d75-desk-holder-v2.3mf')
