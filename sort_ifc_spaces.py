"""Reorder IfcSpace entities in an exported IFC for Thing-IT.

Thing-IT renders spaces by entity id / file order. This script renumbers the
space ids so ascending id follows a fixed type order, and moves each space
record to the matching file position. Every other line is kept byte for byte
(CRLF, exact formatting) so the file stays valid where the old full-rewrite
approach corrupted it.

Usage:
    python sort_ifc_spaces.py "path\\to\\export.ifc"
    -> writes "path\\to\\export_sorted.ifc"
"""

import re
import sys

SPACE_ORDER_FRONT = [
    'meetingroom',
    'privateoffice',
    'enclosedworkspace',
    'openworkspace',
    'focusroom',
]

SPACE_ORDER_BACK = [
    'generic',
    'restroom',
    'operationalroom',
    'cafe',
    'foyer',
    'printstation',
    'storage',
    'corridor',
    'elevator',
    'staircase',
]


def split_args(s):
    out = []
    depth = 0
    cur = ''
    instr = False
    i = 0
    while i < len(s):
        c = s[i]
        if instr:
            if c == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    cur += "''"
                    i += 2
                    continue
                instr = False
                cur += c
            else:
                cur += c
        else:
            if c == "'":
                instr = True
                cur += c
            elif c == '(':
                depth += 1
                cur += c
            elif c == ')':
                depth -= 1
                cur += c
            elif c == ',' and depth == 0:
                out.append(cur)
                cur = ''
            else:
                cur += c
        i += 1
    out.append(cur)
    return out


def unq(x):
    x = x.strip()
    return x[1:-1] if x.startswith("'") and x.endswith("'") else x


def sort_key(longname, name, front, back):
    type_key = (longname or '').strip().lower()
    if type_key in front:
        group, rank = 0, front.index(type_key)
    elif type_key in back:
        group, rank = 2, back.index(type_key)
    else:
        group, rank = 1, 0
    m = re.search(r'(\d+)', name or '')
    number = int(m.group(1)) if m else 0
    alpha = (name or '').strip().lower()
    return (alpha, group, rank, type_key, number)


def remap_refs(line, remap):
    """Replace #<spaceid> references outside quoted strings only."""
    out = []
    instr = False
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if instr:
            out.append(c)
            if c == "'":
                if i + 1 < n and line[i + 1] == "'":
                    out.append(line[i + 1])
                    i += 2
                    continue
                instr = False
            i += 1
        else:
            if c == "'":
                instr = True
                out.append(c)
                i += 1
            elif c == '#':
                j = i + 1
                while j < n and line[j].isdigit():
                    j += 1
                if j > i + 1:
                    rid = int(line[i + 1:j])
                    out.append('#%d' % remap.get(rid, rid))
                    i = j
                else:
                    out.append(c)
                    i += 1
            else:
                out.append(c)
                i += 1
    return ''.join(out)


def main(path):
    raw = open(path, 'rb').read()
    text = raw.decode('latin-1')  # 1:1 byte mapping, reversible

    # Keep exact line content including trailing \r; split on \n only.
    lines = text.split('\n')

    space_pat = re.compile(r"^#(\d+)\s*=\s*IFCSPACE\b", re.IGNORECASE)

    space_idx = []        # line indices holding a space, in file order
    id_by_idx = {}        # line index -> space id
    line_by_id = {}       # space id -> full line text (with trailing \r)
    info = {}             # space id -> (name, longname)

    for idx, line in enumerate(lines):
        m = space_pat.match(line)
        if not m:
            continue
        rid = int(m.group(1))
        space_idx.append(idx)
        id_by_idx[idx] = rid
        line_by_id[rid] = line
        body = line.rstrip('\r').rstrip()
        inner = body[body.index('(') + 1:body.rindex(')')]
        args = split_args(inner)
        name = unq(args[2]) if len(args) > 2 else ''
        longname = unq(args[7]) if len(args) > 7 else ''
        info[rid] = (name, longname)

    if len(space_idx) < 2:
        raise SystemExit("Fewer than 2 IfcSpace records, nothing to sort.")

    positions = sorted(space_idx)
    ascending_ids = sorted(id_by_idx[i] for i in positions)
    desired_ids = sorted(
        ascending_ids,
        key=lambda rid: sort_key(info[rid][1], info[rid][0], SPACE_ORDER_FRONT, SPACE_ORDER_BACK),
    )

    # desired_ids[i] gets the i-th smallest id and sits at the i-th position.
    remap = {desired_ids[i]: ascending_ids[i] for i in range(len(desired_ids))}

    # Build new space line content per position (remap fixes its leading id too).
    new_at_position = {}
    for i, pos in enumerate(positions):
        new_at_position[pos] = remap_refs(line_by_id[desired_ids[i]], remap)

    out_lines = []
    for idx, line in enumerate(lines):
        if idx in new_at_position:
            out_lines.append(new_at_position[idx])
        else:
            out_lines.append(remap_refs(line, remap))

    new_text = '\n'.join(out_lines)

    out_path = re.sub(r'\.ifc$', '_sorted.ifc', path, flags=re.IGNORECASE)
    if out_path == path:
        out_path = path + '_sorted.ifc'
    open(out_path, 'wb').write(new_text.encode('latin-1'))

    print("wrote", out_path)
    print("order (ascending id -> space):")
    for i in range(len(desired_ids)):
        name, longname = info[desired_ids[i]]
        print("  #%d  %s  (%s)" % (ascending_ids[i], name, longname))

    return out_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python sort_ifc_spaces.py <export.ifc>")
    main(sys.argv[1])
