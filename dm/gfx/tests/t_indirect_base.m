// A GPU-written indirect base must reach the driver bank seen by vertices.
#include "../nvn/nvn_mtl.m"
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t *g_mod; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static unsigned checks, failed;
#define CHECK(label,wanted,actual) do { uint64_t w=(wanted),a=(actual);checks++;if(w!=a){fprintf(stderr,"%s: expected %llu got %llu\n",label,w,a);failed++;}}while(0)
int main(void) { @autoreleasepool {
    setvbuf(stdout,NULL,_IONBF,0);mtl_init();NSError *error=nil;
    id<MTLLibrary> lib=[g_dev newLibraryWithSource:
        @"#include <metal_stdlib>\nusing namespace metal;\n"
         "struct A {device uint *out [[id(0)]];constant float4 *c0 [[id(1)]];};\n"
         "vertex void check_base(constant A&a [[buffer(0)]],uint v [[vertex_id]]){a.out[v]=as_type<uint>(a.c0[100].y);}\n"
        options:nil error:&error];
    if(!lib){fprintf(stderr,"%s\n",error.localizedDescription.UTF8String);return 1;}
    NvShader *vs=[NvShader new];vs->stage=0;strcpy(vs->key,"indirect-base-test");
    vs->fn=vs->discard_fn=fn4_note([lib newFunctionWithName:@"check_base"],lib,@"check_base",nil);
    vs->ae=[vs->fn newArgumentEncoderWithBufferIndex:0];vs->arg_len=vs->ae.encodedLength;
    NSDictionary *reflection=@{@"route":@"B",@"drv_reads":@{@"0":@{@"vec4_offsets":@[@0x640],@"dynamic":@NO}},@"bindings":@[
        @{@"kind":@"sbuf",@"reg":@0,@"arg_id":@0,@"msl_name":@"vp_s0",@"msl_type":@"device uint*",@"rw":@YES},
        @{@"kind":@"drvcb",@"bank":@0,@"arg_id":@1,@"msl_name":@"vp_c0",@"msl_type":@"constant float4*"}]};
    char message[160]={0};CHECK("reflection",0,nvn_refl_from_json(reflection,&vs->rf,message,sizeof message));
    size_t bytes=(size_t)getpagesize();uint32_t *memory;if(posix_memalign((void**)&memory,bytes,bytes))return 1;
    for(size_t i=0;i<bytes/4;i++)memory[i]=0xcccccccc;
    mtl_pool_add(memory,bytes);state_reset();S.tf_on=0;S.rast_discard=1;
    // Explicitly bind zero attachments, as OP_SET_RT does. An unset target
    // skips the draw before any vertex storage write can execute.
    memset(&R,0,sizeof R);R.has_rt=1;
    S.has_vp=1;S.vp[0][2]=S.vp[0][3]=1;
    static prog_t pg={.serial=910505};NvProg *program=[NvProg new];program->sh[0]=vs;
    serial_put(pg.serial,program);S.prog=&pg;
    memory[1100]=0;memory[1101]=1;memory[1102]=2;
    uint32_t bases[]={0,128,256};
    for(int indexed=0;indexed<2;indexed++)for(int k=0;k<3;k++){
        unsigned output=(indexed*3+k)*8;uint64_t at=(uint64_t)(memory+1024);
        uint32_t record[5]={3,1,0,0,0};record[indexed?4:3]=bases[k];
        S.ssbo[0][0]=(p_bind_buf){.stage=0,.index=0,.addr=(uint64_t)(memory+output),.size=32};
        p_draw arrays={.prim=NVN_DRAW_PRIMITIVE_POINTS,.count=3,.instances=1,.ind=at};
        p_draw_idx elements={.prim=NVN_DRAW_PRIMITIVE_POINTS,.count=3,.instances=1,.itype=2,.ibuf=(uint64_t)(memory+1100),.ind=at};
        mtl_sub_begin();mtl_sub_update(record,at,indexed?20:16);g_draw_binst=999;
        CHECK("indirect record admitted",1,draw_indirect_base(program,indexed?NULL:&arrays,indexed?&elements:NULL));
        CHECK("GPU-written base",bases[k],g_draw_binst);
        uint64_t waits=g_mdi_waits;
        CHECK("repeat read",1,draw_indirect_base(program,indexed?NULL:&arrays,indexed?&elements:NULL));
        CHECK("same boundary reused",waits,g_mdi_waits);
        if(getenv("DM_TEST_INDIRECT_BASE_OLD"))vs->rf.drv_binst=0;
        uint64_t draws=g_stat_draw;
        draw(indexed?NULL:&arrays,indexed?&elements:NULL);vs->rf.drv_binst=1;
        CHECK("draw encoded",1,g_stat_draw-draws);
        CHECK("GPU completed",1,mtl_wait(mtl_sub_commit(),5000000000ull));
        CHECK("GPU error",0,mtl_last_commit_error());
        for(int v=0;v<8;v++)CHECK("driver value or guard",v<3?bases[k]:0xcccccccc,memory[output+v]);
    }
    p_draw direct={0};CHECK("direct draw needs no readback",0,draw_indirect_base(program,&direct,NULL));
    mtl_pool_del(memory);mtl_drain();free(memory);
    printf("INDIRECT_BASE checks=%u failed=%u\n",checks,failed);return failed!=0;
} }
