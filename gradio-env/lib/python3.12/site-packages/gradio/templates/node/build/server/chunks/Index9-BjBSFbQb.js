import { K as h, L as tick } from './2-CaEpGcoe.js';
import { p } from './statustracker-ColKCG6D.js';
import { n } from './src3-CHMGbv-A.js';
import { r } from './Index7-BQIee8JR.js';
import './async-Cv1-GZGV.js';
import { d as derived, s as spread_props, a as attr_class, e as escape_html, b as attr_style, c as bind_props } from './renderer-RGQlaTg4.js';
import './environment-C8sqWbA_.js';
import './chunk-B3kRsjbd.js';
import 'node:module';
import './server-BDON6J25.js';
import './html-CfyvkLET.js';

function o(e,t){e.component(e=>{let{open:n=true,label:r=``,onexpand:i,oncollapse:o,children:s}=t;e.push(`<button${attr_class(`label-wrap svelte-e5lyqv`,void 0,{open:n})}><span class="svelte-e5lyqv">${escape_html(r)}</span> <span class="icon svelte-e5lyqv"${attr_style(``,{transform:n?`rotate(0)`:`rotate(90deg)`})}>▼</span></button> <div data-testid="accordion-content"${attr_style(``,{display:n?`block`:`none`})}>`),s?.(e),e.push(`<!----></div>`),bind_props(t,{open:n});});}function s(s,c){s.component(s=>{let{$$slots:l,$$events:u,...d}=c;class f extends h{set_data(e){let t=this.props.open;super.set_data(e),`open`in e&&e.open!==t&&(e.open?(this.dispatch(`expand`),tick().then(()=>this.dispatch(`gradio_expand`))):this.dispatch(`collapse`)),this.shared.loading_status.status=`complete`;}}let p$1=new f(d),m=derived(()=>p$1.shared.label||``),h$1=derived(()=>[...p$1.shared.elem_classes||[],`gr-accordion`]),g=derived(()=>p$1.shared.visible===true?true:`hidden`);n(s,{elem_id:p$1.shared.elem_id,elem_classes:h$1(),visible:g(),children:e=>{p$1.shared.loading_status?(e.push(`<!--[0-->`),p(e,spread_props([{autoscroll:p$1.shared.autoscroll,i18n:p$1.i18n},p$1.shared.loading_status]))):e.push(`<!--[-1-->`),e.push(`<!--]--> `),o(e,{label:m(),open:p$1.props.open,onexpand:()=>{p$1.dispatch(`expand`),p$1.dispatch(`gradio_expand`);},oncollapse:()=>p$1.dispatch(`collapse`),children:e=>{r(e,{children:e=>{d.children?.(e),e.push(`<!---->`);},$$slots:{default:true}});},$$slots:{default:true}}),e.push(`<!---->`);},$$slots:{default:true}});});}

export { s as default };
//# sourceMappingURL=Index9-BjBSFbQb.js.map
