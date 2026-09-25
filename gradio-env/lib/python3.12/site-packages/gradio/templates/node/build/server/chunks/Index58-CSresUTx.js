import { K as h } from './2-CaEpGcoe.js';
import { r } from './Index7-BQIee8JR.js';
import { a as a$1 } from './Index56-CaYEFR39.js';
import { g as getContext, f as attr, a as attr_class, i as stringify, b as attr_style, o as store_get, u as unsubscribe_stores, d as derived } from './renderer-RGQlaTg4.js';
import './async-Cv1-GZGV.js';
import './environment-C8sqWbA_.js';
import './chunk-B3kRsjbd.js';
import 'node:module';
import './statustracker-ColKCG6D.js';
import './src3-CHMGbv-A.js';
import './html-CfyvkLET.js';
import './server-BDON6J25.js';

function a(e,a){e.component(e=>{var o;let{elem_id:s=``,elem_classes:c=[],label:l,id:u,visible:d,interactive:f,order:p,alignment:m=`left`,scale:h,component_id:g,onselect:_,children:v}=a,{register_tab:y,unregister_tab:b,selected_tab:x,selected_tab_index:S}=getContext(a$1),C=derived(()=>u??g);let w=derived(()=>d!==false&&d!==`hidden`);e.push(`<div${attr(`id`,s)}${attr_class(`tabitem ${stringify(c.join(` `))}`,`svelte-dmtrd3`,{"grow-children":h>=1})} role="tabpanel"${attr_style(``,{display:store_get(o??={},`$selected_tab`,x)===C()&&w()?`flex`:`none`,"flex-grow":h})}>`),r(e,{scale:h>=1?h:null,children:e=>{v?.(e),e.push(`<!---->`);},$$slots:{default:true}}),e.push(`<!----></div>`),o&&unsubscribe_stores(o);});}function o(t,n){t.component(t=>{let{$$slots:r,$$events:i,...o}=n,s=new h(o);a(t,{elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,label:s.shared.label,visible:s.shared.visible,interactive:s.shared.interactive,id:s.props.id,order:s.props.order,alignment:s.props.alignment,scale:s.shared.scale,component_id:s.props.component_id,onselect:e=>s.dispatch(`select`,e),children:e=>{o.children?.(e),e.push(`<!---->`);}});});}

export { a as BaseTabItem, o as default };
//# sourceMappingURL=Index58-CSresUTx.js.map
