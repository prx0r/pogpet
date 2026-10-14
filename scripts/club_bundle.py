#!/usr/bin/env python3
"""Pogtown Comedy Club: turn a rivelab director plan into a static site bundle.

    python3 scripts/club_bundle.py <plan.json> [--mp4 <render.mp4>] [--id <set_id>] [--title "..."]
                                   [--club-riv <club.riv>] [--out site/assets/club] [--mp4-height 1280]

Reads the director output (rivelab director/direct.py -> plans/<id>.plan.json: char_riv, club_riv, audio,
audio_offset, vm tracks, club tracks, events, captions, tag) and writes

    <out>/club.riv                    shared club (ClubBack / ClubFront artboards), copied once
    <out>/<id>/<id>.riv               the character (artboard Character, state machine Acting)
    <out>/<id>/set.json               baked keyframes: vm + club tracks simplified, events, captions, tag
    <out>/<id>/set.m4a                set audio, already delayed by audio_offset (so t == audio.currentTime)
    <out>/<id>/set.mp4 + poster.jpg   the rendered proof MP4 (re-encoded for the web) - player + feed fallback
    <out>/manifest.json               list of sets the Videos tab offers (upserted by id)

Relative paths inside the plan resolve against the rivelab root (the plan's parent's parent).
Skins marked "private": true in skins/<id>/skin.json are refused. Needs ffmpeg on PATH.
"""
import argparse, json, os, shutil, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument('plan')
ap.add_argument('--mp4', help='rendered MP4 of the same plan (director/render.py output)')
ap.add_argument('--id', help='set id (default: plan file name before ".plan")')
ap.add_argument('--title', help='picker label (default: plan tag name)')
ap.add_argument('--club-riv', help='override the club .riv')
ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site', 'assets', 'club'))
ap.add_argument('--mp4-height', type=int, default=1280, help='re-encode height for the web MP4 (0 = copy as is)')
ap.add_argument('--eps', type=float, default=0.004, help='track simplification tolerance (view-model units)')
a = ap.parse_args()

plan_path = os.path.abspath(a.plan)
plan = json.load(open(plan_path))
root = os.path.dirname(os.path.dirname(plan_path))
sid = a.id or os.path.basename(plan_path).split('.')[0]
if not sid.replace('_', '').replace('-', '').isalnum():
    sys.exit('bad set id %r' % sid)


def res(p):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(root, p))


skin = os.path.join(root, 'skins', sid, 'skin.json')
if os.path.exists(skin) and json.load(open(skin)).get('private'):
    sys.exit('refusing: skin %r is marked private' % sid)

out = os.path.abspath(a.out)
sd = os.path.join(out, sid)
os.makedirs(sd, exist_ok=True)


def simplify(tr, eps):
    """Drop samples that linear interpolation of the kept neighbours reproduces within eps."""
    if len(tr) <= 2:
        return [[round(t, 3), round(v, 4)] for t, v in tr]
    keep = [tr[0]]
    for i in range(1, len(tr) - 1):
        a0, b, c = keep[-1], tr[i], tr[i + 1]
        u = (b[0] - a0[0]) / max(1e-9, c[0] - a0[0])
        if abs(a0[1] + (c[1] - a0[1]) * u - b[1]) > eps:
            keep.append(b)
    keep.append(tr[-1])
    return [[round(t, 3), round(v, 4)] for t, v in keep]


def run(cmd):
    subprocess.run(cmd, check=True)


dur = float(plan['duration'])
# 1. rivs
char_riv = res(plan['char_riv'])
shutil.copy(char_riv, os.path.join(sd, sid + '.riv'))
shutil.copy(res(a.club_riv or plan['club_riv']), os.path.join(out, 'club.riv'))

# 2. audio, pre-delayed so the player clock is simply audio.currentTime
has_audio = bool(plan.get('audio'))
if has_audio:
    off_ms = int(round(float(plan.get('audio_offset', 0)) * 1000))
    af = 'adelay=%d:all=1,apad' % off_ms if off_ms > 0 else 'apad'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', res(plan['audio']), '-af', af, '-t', str(dur),
         '-ac', '1', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', os.path.join(sd, 'set.m4a')])

# 3. mp4 + poster
has_mp4 = bool(a.mp4)
if has_mp4:
    dst = os.path.join(sd, 'set.mp4')
    if a.mp4_height:
        run(['ffmpeg', '-y', '-loglevel', 'error', '-i', a.mp4, '-vf', 'scale=-2:%d' % a.mp4_height,
             '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', dst])
    else:
        shutil.copy(a.mp4, dst)
    run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(min(4.0, dur / 3)), '-i', dst, '-frames:v', '1',
         '-vf', 'scale=-2:960', '-q:v', '5', os.path.join(sd, 'poster.jpg')])

# 4. baked keyframes
tag = plan.get('tag') or {}
bundle = {
    'id': sid, 'version': 1,
    'duration': dur, 'fps': plan.get('fps', 30),
    'artboard': plan.get('artboard', 'Character'), 'stateMachine': 'Acting',
    'world': plan.get('world', ''), 'char_place': plan.get('char_place', {}),
    'init': plan.get('init', {}),
    'vm': {k: simplify(v, a.eps) for k, v in (plan.get('vm') or {}).items()},
    'club': {k: simplify(v, a.eps) for k, v in (plan.get('club') or {}).items()},
    'events': [{k: (round(v, 3) if k == 't' else v) for k, v in e.items()} for e in plan.get('events', [])],
    'captions': [{'t0': round(c['t0'], 3), 't1': round(c['t1'], 3),
                  'words': [{'w': w['w'], 't0': round(w['t0'], 3), 't1': round(w['t1'], 3)} for w in c['words']]}
                 for c in plan.get('captions', [])],
    'tag': tag, 'fadeIn': plan.get('fadeIn', 0), 'fadeOut': plan.get('fadeOut', 0),
}
json.dump(bundle, open(os.path.join(sd, 'set.json'), 'w'), separators=(',', ':'))

# 5. manifest
mp = os.path.join(out, 'manifest.json')
man = json.load(open(mp)) if os.path.exists(mp) else {'club_riv': 'club.riv', 'sets': []}
entry = {
    'id': sid, 'title': a.title or tag.get('name') or sid.title(), 'sub': tag.get('sub', ''),
    'color': tag.get('color', '#c4891a'), 'duration': dur,
    'riv': '%s/%s.riv' % (sid, sid), 'set': '%s/set.json' % sid,
    'audio': '%s/set.m4a' % sid if has_audio else None,
    'mp4': '%s/set.mp4' % sid if has_mp4 else None,
    'poster': '%s/poster.jpg' % sid if has_mp4 else None,
}
man['sets'] = [s for s in man['sets'] if s['id'] != sid] + [entry]
json.dump(man, open(mp, 'w'), indent=1)
sizes = {f: os.path.getsize(os.path.join(sd, f)) // 1024 for f in sorted(os.listdir(sd))}
print(json.dumps({'id': sid, 'out': sd, 'kb': sizes}))
