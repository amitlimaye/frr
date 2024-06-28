#ifdef HAVE_CONFIG_H
#include "config.h" /* Include this explicitly */
#endif

#include "lib/libfrr.h"

#include "zebra/debug.h"
#include "zebra/interface.h"
#include "zebra/zebra_dplane.h"
#include "zebra/debug.h"

static const char *module_name = "HH plugin";
static struct zebra_dplane_provider *prov_p;
void *data = NULL;


static int hh_start(struct zebra_dplane_provider *prov){
    // Nothing to do right now 
    // here ideally we should start our own thread to talk to our API
    zlog_err("Initializing module %s",module_name);
    return 0;
}
static int hh_finish(struct zebra_dplane_provider *prov,bool early){
    //disconnect go away 
    return 0;
}

static int hh_process_update(struct zebra_dplane_ctx *ctx){
    switch (dplane_ctx_get_op(ctx)) {
    case DPLANE_OP_ROUTE_INSTALL:
    break;
	case DPLANE_OP_ROUTE_UPDATE:
    break;
	case DPLANE_OP_ROUTE_DELETE:
    break;
	case DPLANE_OP_ROUTE_NOTIFY:
    break;

	/* Nexthop update */
	case DPLANE_OP_NH_INSTALL:
    break;
	case DPLANE_OP_NH_UPDATE:
    break;
	case DPLANE_OP_NH_DELETE:
    break;
    case DPLANE_OP_SYS_ROUTE_ADD:
    break;
	case DPLANE_OP_SYS_ROUTE_DELETE:
    break;

	/* Interface address update */
	case DPLANE_OP_ADDR_INSTALL:
    zlog_info("Dplane OP Addr install");
    break;
	case DPLANE_OP_ADDR_UNINSTALL:
    break;

	/* MAC address update */
	case DPLANE_OP_MAC_INSTALL:
    zlog_info("Dplane OP MAC Addr install");
    break;
	case DPLANE_OP_MAC_DELETE:
    break;

	/* EVPN neighbor updates */
	case DPLANE_OP_NEIGH_INSTALL:
    zlog_info("EVPN neighbor Install");
    break;
	case DPLANE_OP_NEIGH_UPDATE:
    break;
	case DPLANE_OP_NEIGH_DELETE:
    break;

	/* EVPN VTEP updates */
	case DPLANE_OP_VTEP_ADD:
    zlog_info("EVPN VTEP Add");
    break;
	case DPLANE_OP_VTEP_DELETE:
    break;

    /* bridge port update */
    case DPLANE_OP_BR_PORT_UPDATE:
        break;
    case DPLANE_OP_INTF_ADDR_ADD:
	case DPLANE_OP_INTF_ADDR_DEL:

	/* Incoming interface config events */
	case DPLANE_OP_INTF_NETCONFIG:

	/* Interface update */
	case DPLANE_OP_INTF_INSTALL:
	case DPLANE_OP_INTF_UPDATE:
	case DPLANE_OP_INTF_DELETE:
    default:
        zlog_debug("Received unhandled OP %d",dplane_ctx_get_op(ctx));
    }
}

static int hh_process(struct zebra_dplane_provider *prov){
    struct zebra_dplane_ctx *ctx;
	int counter, limit;

	if (IS_ZEBRA_DEBUG_DPLANE_DPDK_DETAIL)
		zlog_debug("processing %s", dplane_provider_get_name(prov));

	limit = dplane_provider_get_work_limit(prov);
	for (counter = 0; counter < limit; counter++) {
		ctx = dplane_provider_dequeue_in_ctx(prov);
		if (!ctx)
			break;
        int status = hh_process_update(ctx);
    }
    return 0;
}

static int init_hh_plugin(struct event_loop *tm){
    int ret = dplane_provider_register(module_name,
    DPLANE_PRIO_PRE_KERNEL,
    DPLANE_PROV_FLAGS_DEFAULT,
    hh_start,
    hh_process,
    hh_finish,
    data,
    &prov_p);
    if (ret < 0) {
        zlog_debug("Provider registration failed %d",ret);
        return ret;
    }   
    zlog_info("Registered module %s",module_name);
    return 0;
}


/*
 * Base FRR loadable module info: basic info including module entry-point.
 */
static int module_init(void)
{
    zlog_info("Initializing module %s",module_name);
	hook_register(frr_late_init, init_hh_plugin);
	return 0;
}

FRR_MODULE_SETUP(
	.name = "dplane_hh",
	.version = "0.0.1",
	.description = "HH test Plugin",
	.init = module_init,
);