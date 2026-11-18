#define _GNU_SOURCE
#include <dlfcn.h>
#include <stddef.h>

/* Minimal libmpv ABI wrapper enabling config + auto-safe hardware decoding inside Stremio. */
typedef int (*fn_mpv_initialize)(void *ctx);
typedef int (*fn_mpv_set_option_string)(void *ctx, const char *name, const char *data);

static fn_mpv_initialize real_mpv_initialize = NULL;
static fn_mpv_set_option_string real_mpv_set_option_string = NULL;

static void *resolve_one(const char *sym) {
    void *p = dlsym(RTLD_NEXT, sym);
    if (!p) {
        void *h = dlopen("libmpv.so.2", RTLD_LAZY | RTLD_NOLOAD);
        if (h) {
            p = dlsym(h, sym);
        }
    }
    return p;
}

int mpv_initialize(void *ctx) {
    if (!real_mpv_initialize) {
        real_mpv_initialize = (fn_mpv_initialize)resolve_one("mpv_initialize");
    }
    if (!real_mpv_set_option_string) {
        real_mpv_set_option_string = (fn_mpv_set_option_string)resolve_one("mpv_set_option_string");
    }
    if (!real_mpv_initialize) {
        return -1;
    }
    if (real_mpv_set_option_string) {
        real_mpv_set_option_string(ctx, "config", "yes");
        real_mpv_set_option_string(ctx, "hwdec", "auto-safe");
        real_mpv_set_option_string(ctx, "hwdec-codecs", "all");
    }
    return real_mpv_initialize(ctx);
}
