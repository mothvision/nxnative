"""Exercise production native-texture output functions with a fake decoder/GPU.

The full host build checks the real types and linkage. This small C harness checks
output ownership without requiring game files, VideoToolbox or a Metal device.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]


class MovieTextureTests(unittest.TestCase):
    def test_native_copy_releases_outputs_and_resumes_pending_decode(self):
        source = (REPO / 'dm/host/hle_movie.c').read_text()
        start = source.index('static void md_release_output(')
        end = source.index('\nHLE_FORCE(', start)
        functions = source[start:end]
        harness = r'''
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stddef.h>
typedef struct {
    pthread_mutex_t mu;
    struct { int used, pic; void *frm; } out[16];
    int npend, avc_drain, red_dec, red_img, w, h;
} mdec_t;
#define dm_host_mutex_lock pthread_mutex_lock
static int writes, signals, pumps, bad_texture, bad_sync;
static unsigned char pixels[16];
static void *get_data(const void *b) { return (void *)b; }
static size_t get_cap(const void *b) { (void)b; return 8; }
static void *get_sync(const void *b) { (void)b; return &signals; }
static struct {
    void *(*data)(const void *);
    size_t (*cap)(const void *);
    void *(*nvn_sync)(const void *);
} G = {get_data, get_cap, get_sync};
static void *guest_sym(const char *name) { (void)name; return get_sync; }
static void md_pump(mdec_t *d) { (void)d; ++pumps; }
#define LOG(...) ((void)0)
#define MD_TRACE(...) ((void)0)
static int nvn_host_write_texture(const void *t, const void *src, int w, int h,
                                 size_t row, int *tw, int *th) {
    (void)t; (void)w; (void)h; (void)row;
    if (bad_texture) return -1;
    if (tw) *tw = 2;
    if (th) *th = 2;
    if (src) ++writes;
    return 0x25;
}
static int nvn_host_signal_sync(void *s) {
    (void)s; assert(writes == signals + 1); ++signals; return bad_sync;
}
'''
        harness += functions
        harness += r'''
int main(void) {
    mdec_t d = {.mu = PTHREAD_MUTEX_INITIALIZER, .w = 2, .h = 2};
    int texture;
    for (int frame = 0; frame < 100; ++frame) {
        int i = frame % 16;
        assert(!d.out[i].used);
        d.out[i].used = d.out[i].pic = 1; d.out[i].frm = pixels;
        d.npend = frame % 2; d.avc_drain = frame % 3 == 0;
        int before = pumps;
        assert(md_out_tex(&d, i, &texture) == 0);
        assert(!d.out[i].used && !d.out[i].pic);
        assert(pumps == before + !!(d.npend || d.avc_drain));
    }
    assert(writes == 100 && signals == 100);
    d.out[0].used = d.out[0].pic = 1;
    bad_texture = 1;
    assert(md_out_tex(&d, 0, &texture) == 0x100b);
    assert(d.out[0].used && d.out[0].pic);
    bad_texture = 0; d.npend = d.avc_drain = 0;
    d.out[0].pic = 0; G.nvn_sync = 0;
    assert(md_out_tex(&d, 0, &texture) == 0);
    assert(!d.out[0].used && writes == 100);
    pthread_mutex_destroy(&d.mu);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            code, binary = Path(tmp) / 'movie.c', Path(tmp) / 'movie'
            code.write_text(harness)
            subprocess.run(['clang', '-std=c11', '-O1', '-Wall', '-Werror',
                            '-Wno-unused-variable', '-pthread', str(code), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
