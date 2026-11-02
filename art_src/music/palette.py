#!/usr/bin/env python3
"""The instruments Groundhold's music and cues play, and the free libraries they come from.

Every library here lets us ship audio rendered from it (each one's licence was read at its source, see LIBRARIES),
none is ever committed to git: the music image (art_src/music/Dockerfile) fetches them at a pinned commit, and only
the files the palette names. A piece names its instruments by the ids in INSTRUMENTS; a new instrument is added here
first, with why it is in the palette, and the image is built again.

    python3 art_src/music/palette.py --patterns vsco      # the image's sparse-checkout patterns for a library
    python3 art_src/music/palette.py --list               # every instrument, its library and what it is for

Standard library only: the image's build stage runs it before Python's packages are installed.
"""

from __future__ import annotations

import sys

# Where the image keeps each library (the Dockerfile's FETCH stage writes them there).
SOUNDS = '/opt/sounds'

LIBRARIES = {
    'vsco': {
        'name': 'VSCO 2 Community Edition 1.1.0',
        'by': 'Versilian Studios (Sam Gossner)',
        'licence': 'CC0 1.0 (public domain dedication; the repository\'s LICENSE)',
        'source': 'https://github.com/sgossner/VSCO-2-CE',
        'commit': '28092772094b2d9f1148d84cea97f4545b8c687d',   # tag 1.1.0, the SFZ release
        'for': 'the orchestra: string sections, horn, brass, woodwinds, harp, timpani',
    },
    'vcsl': {
        'name': 'Versilian Community Sample Library 1.2.2-RC',
        'by': 'Versilian Studios (Sam Gossner) and its contributors',
        'licence': 'CC0 1.0 (public domain dedication; the repository\'s LICENSE)',
        'source': 'https://github.com/sgossner/VCSL',
        'commit': 'b6e6ac82d22248edee98a0bde185eb9ef6d439ad',   # tag v1.2.2-RC, the SFZ release
        'for': 'the folk band and the bells: folk harp, strumstick, psaltery, recorders, frame drum, hand chimes',
    },
    'fluidr3': {
        'name': 'FluidR3 GM',
        'by': 'Frank Wen (and Toby Smithe\'s packaging)',
        'licence': 'MIT (Debian\'s fluid-soundfont-gm copyright file)',
        'source': 'https://packages.debian.org/trixie/fluid-soundfont-gm',
        'commit': 'Debian trixie, fluid-soundfont-gm 3.1',
        'for': 'what the CC0 sets lack: a choir pad, and a General MIDI bank for quick drafts',
    },
}

# Considered and left out, so the next agent need not look again (licences read 2 November 2026):
REJECTED = {
    'Sonatina Symphonic Orchestra': 'Creative Commons Sampling Plus 1.0, a licence CC has retired, which excludes '
                                    'advertising use (a trailer); built from other sets\' samples. VSCO 2 CE covers it '
                                    'under CC0.',
    'GeneralUser GS 2.0.3': 'its own licence allows music made with it, but its author cannot be sure where all its '
                            'samples came from (documentation/LICENSE.txt); Cyberworld kept FluidR3 GM over it for '
                            'the same reason. A comparison by ear may add it to the image.',
    'Salamander Grand Piano': 'CC-BY 3.0, fine to use, but no piano is in the palette; VCSL\'s Steinway B (CC0) '
                              'would come first.',
}

# id: (library, file inside it or (bank, program) for a soundfont, what it is for)
INSTRUMENTS = {
    # the orchestra (VSCO 2 CE)
    'violins': ('vsco', 'ViolinEnsSusVib.sfz', 'the violin section, sustained with vibrato: lines and high pads'),
    'violins_trem': ('vsco', 'ViolinEnsTrem.sfz', 'the violin section in tremolo: a shimmer under a swell'),
    'violins_pizz': ('vsco', 'ViolinEnsPizz.sfz', 'the violins plucked: a light walking figure'),
    'violas': ('vsco', 'ViolaEnsSusVib.sfz', 'the violas: the inner voice'),
    'celli': ('vsco', 'CelloEnsSusVib.sfz', 'the cello section: the warm bass line and counter-melody'),
    'celli_pizz': ('vsco', 'CelloEnsPizz.sfz', 'the celli plucked: a bass that walks'),
    'basses': ('vsco', 'ContrabassSusVB.sfz', 'a contrabass under the celli, an octave down: the floor'),
    'fiddle': ('vsco', 'SViolinVib.sfz', 'a solo violin: the folk fiddle\'s voice'),
    'horn': ('vsco', 'FHornSus.sfz', 'the French horn: the call, the theme\'s bronze voice'),
    'horn_stac': ('vsco', 'FHornStac.sfz', 'the horn short: a call\'s pickups'),
    'trumpet': ('vsco', 'TrumpetSus.sfz', 'the trumpet: a summation\'s top, sparingly'),
    'trombone': ('vsco', 'TromboneSus.sfz', 'the trombone: low brass chords'),
    'tuba': ('vsco', 'TubaSus.sfz', 'the tuba: the brass floor'),
    'flute': ('vsco', 'FluteSusVib.sfz', 'the flute with vibrato: a lyric line'),
    'flute_nv': ('vsco', 'FluteSusNV.sfz', 'the flute without vibrato: air, a whistle\'s plainness'),
    'oboe': ('vsco', 'OboeSusVib.sfz', 'the oboe: a plaintive answer'),
    'clarinet': ('vsco', 'ClarinetSus.sfz', 'the clarinet: a soft inner line'),
    'bassoon': ('vsco', 'BassoonSus.sfz', 'the bassoon: a woody bass under a folk band'),
    'harp': ('vsco', 'Harp.sfz', 'the concert harp: ostinati and rolled chords'),
    'timpani': ('vsco', 'Timpani.sfz', 'timpani strokes on the roots'),
    'timpani_roll': ('vsco', 'TimpaniRolls.sfz', 'a timpani roll into a summation'),
    'glockenspiel': ('vsco', 'Glockenspiel.sfz', 'the glockenspiel: a glint on a melody\'s top'),
    # the folk band and the bells (VCSL)
    'folk_harp': ('vcsl', 'Chordophones/Composite Chordophones/Folk Harp.sfz',
                  'a folk harp: a lap harp\'s close, bright pluck'),
    'concert_harp': ('vcsl', 'Chordophones/Composite Chordophones/Concert Harp.sfz', 'a second concert harp'),
    'strumstick': ('vcsl', 'Chordophones/Composite Chordophones/Strumstick.sfz',
                   'a strumstick (a dulcimer\'s cousin): drone and melody strings together'),
    'psaltery': ('vcsl', 'Chordophones/Zithers/Psaltery, Bowed and Plucked - Pluck.sfz', 'a psaltery plucked'),
    'psaltery_bowed': ('vcsl', 'Chordophones/Zithers/Psaltery, Bowed and Plucked - LongBow.sfz',
                       'a psaltery bowed: a glassy, breathing drone'),
    'recorder': ('vcsl', 'Aerophones/Edge-blown Aerophones/Baroque Soprano Recorder - Sustain.sfz',
                 'a soprano recorder: the whistle\'s colour'),
    'alto_recorder': ('vcsl', 'Aerophones/Edge-blown Aerophones/Baroque Alto Recorder - SusVib.sfz',
                      'an alto recorder with vibrato: a softer, lower whistle'),
    'ocarina': ('vcsl', 'Aerophones/Edge-blown Aerophones/Ocarina, Typical - SusVib.sfz',
                'an ocarina: a hollow, round voice'),
    'frame_drum': ('vcsl', 'Membranophones/Struck Membranophones/Frame Drum.sfz',
                   'a frame drum: the bodhran\'s place in the band'),
    'bass_drum': ('vcsl', 'Membranophones/Struck Membranophones/Bass Drum 1.sfz', 'a bass drum: a far, deep stroke'),
    'tom': ('vcsl', 'Membranophones/Struck Membranophones/Tom 1.sfz', 'a tom with mallets: a march\'s low voice'),
    'snare_rope': ('vcsl', 'Membranophones/Struck Membranophones/Snare Drum, Rope Tension.sfz',
                   'a rope-tension field drum: a march, never a kit'),
    'hand_chimes': ('vcsl', 'Idiophones/Struck Idiophones/Hand Chimes.sfz', 'hand chimes: a clear, soft bell'),
    'hand_bells': ('vcsl', 'Idiophones/Struck Idiophones/Hand Bells, Nepalese.sfz', 'small hand bells'),
    'tubular_bells': ('vcsl', 'Idiophones/Struck Idiophones/Tubular Bells 1.sfz', 'tubular bells: the far bell'),
    'mark_tree': ('vcsl', 'Idiophones/Struck Idiophones/Mark Trees.sfz', 'a mark tree: a glitter into a section'),
    'sus_cymbal': ('vcsl', 'Idiophones/Struck Idiophones/Suspended Cymbal 1.sfz', 'a suspended cymbal: a swell'),
    'triangle': ('vcsl', 'Idiophones/Struck Idiophones/Triangles.sfz', 'a triangle'),
    'woodblock': ('vcsl', 'Idiophones/Struck Idiophones/Woodblock.sfz', 'a woodblock: the focus tick\'s wood'),
    'wine_glass': ('vcsl', 'Idiophones/Friction Idiophones/Wine Glasses - Slow.sfz', 'a rubbed glass: the Tide\'s hum'),
    'ocean_drum': ('vcsl', 'Membranophones/Other Membranophones/Ocean Drum.sfz', 'an ocean drum: surf on a skin'),
    # what the CC0 sets lack (FluidR3 GM)
    'choir': ('fluidr3', (0, 52), 'Choir Aahs: a soft pad of voices, never exposed'),
    'voices': ('fluidr3', (0, 53), 'Voice Oohs: a closed-mouth pad'),
    'gm_whistle': ('fluidr3', (0, 78), 'a General MIDI whistle, for drafts only'),
    'gm_bagpipe': ('fluidr3', (0, 109), 'a General MIDI bagpipe drone, for drafts only'),
}


def path_of(inst: str) -> str:
    """The instrument's file in the image (an .sfz, or the soundfont an SF2 preset is in)."""
    lib, where, _ = INSTRUMENTS[inst]
    if lib == 'fluidr3':
        return '/usr/share/sounds/sf2/FluidR3_GM.sf2'
    return f'{SOUNDS}/{lib}/{where}'


def kind_of(inst: str) -> str:
    return 'sf2' if INSTRUMENTS[inst][0] == 'fluidr3' else 'sfz'


# The sample folders each SFZ reads, as git sparse-checkout patterns (non-cone), so the image fetches only those.
# VSCO's SFZ files sit at its root and read from folders named in their default_path; VCSL's sit beside their folder.
VSCO_FOLDERS = {
    'ViolinEnsSusVib.sfz': 'Strings/Violin Section/susVib', 'ViolinEnsTrem.sfz': 'Strings/Violin Section/Trem',
    'ViolinEnsPizz.sfz': 'Strings/Violin Section/Pizz', 'ViolaEnsSusVib.sfz': 'Strings/Viola Section/susvib',
    'CelloEnsSusVib.sfz': 'Strings/Cello Section/susvib', 'CelloEnsPizz.sfz': 'Strings/Cello Section/pizzT',
    'ContrabassSusVB.sfz': 'Strings/Solo Contrabass/SusVib', 'SViolinVib.sfz': 'Strings/Solo Violin/Arco Vib',
    'FHornSus.sfz': 'Brass/F Horn/sus', 'FHornStac.sfz': 'Brass/F Horn/stac', 'TrumpetSus.sfz': 'Brass/Trumpet/sus',
    'TromboneSus.sfz': 'Brass/Tenor Trombone/sus', 'TubaSus.sfz': 'Brass/Tuba/sus',
    'FluteSusVib.sfz': 'Woodwinds/Flute/susvib', 'FluteSusNV.sfz': 'Woodwinds/Flute/susNV',
    'OboeSusVib.sfz': 'Woodwinds/Oboe/Vib', 'ClarinetSus.sfz': 'Woodwinds/Clarinet/susLong',
    'BassoonSus.sfz': 'Woodwinds/Bassoon/sus', 'Harp.sfz': 'Strings/Harp', 'Timpani.sfz': 'Percussion/Timpani',
    'TimpaniRolls.sfz': 'Percussion/Timpani/Rolls', 'Glockenspiel.sfz': 'Percussion/Glock',
}
VCSL_FOLDERS = {
    'Folk Harp.sfz': ['Folk Harp'], 'Concert Harp.sfz': ['Concert Harp'], 'Strumstick.sfz': ['Strumstick/Finger'],
    'Psaltery, Bowed and Plucked - Pluck.sfz': ['Psaltery, Bowed and Plucked/Pluck'],
    'Psaltery, Bowed and Plucked - LongBow.sfz': ['Psaltery, Bowed and Plucked/LongBow'],
    'Baroque Soprano Recorder - Sustain.sfz': ['Baroque Soprano Recorder/Sustain'],
    'Baroque Alto Recorder - SusVib.sfz': ['Baroque Alto Recorder/SusVib'],
    'Ocarina, Typical - SusVib.sfz': ['Ocarina, Typical/Releases/SusVib', 'Ocarina, Typical/Sustains/SusVib'],
    'Frame Drum.sfz': ['Frame Drum'], 'Bass Drum 1.sfz': ['Bass Drum 1'], 'Tom 1.sfz': ['Tom 1'],
    'Snare Drum, Rope Tension.sfz': ['Snare Drum, Rope Tension'], 'Hand Chimes.sfz': ['Hand Chimes'],
    'Hand Bells, Nepalese.sfz': ['Hand Bells, Nepalese'], 'Tubular Bells 1.sfz': ['Tubular Bells 1'],
    'Mark Trees.sfz': ['Mark Trees/Legacy'], 'Suspended Cymbal 1.sfz': ['Suspended Cymbal 1'],
    'Triangles.sfz': ['Triangles'], 'Woodblock.sfz': ['Woodblock'],
    'Wine Glasses - Slow.sfz': ['Wine Glasses/Releases/Slow', 'Wine Glasses/Sustains/Slow'],
    'Ocean Drum.sfz': ['Ocean Drum'],
}


def patterns(lib: str) -> list[str]:
    """Non-cone sparse-checkout patterns: each SFZ the palette names and the folder of samples it reads."""
    files = sorted({where for l, where, _ in INSTRUMENTS.values() if l == lib})
    out = []
    for f in files:
        if lib == 'vsco':
            out += [f'/{f}', f'/{VSCO_FOLDERS[f]}/']
        else:
            parent = f.rsplit('/', 1)[0]
            out.append(f'/{f}')
            out += [f'/{parent}/{d}/' for d in VCSL_FOLDERS[f.rsplit('/', 1)[1]]]
    return out


def main(argv: list[str]) -> int:
    if argv[:1] == ['--patterns'] and len(argv) == 2:
        print('\n'.join(patterns(argv[1])))
        return 0
    if argv[:1] == ['--list']:
        for inst, (lib, where, why) in INSTRUMENTS.items():
            print(f'{inst:15s} {lib:8s} {why}')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
