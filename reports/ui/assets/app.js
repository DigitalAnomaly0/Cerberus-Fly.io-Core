
async function fetchJSON(path){ const r=await fetch(path); if(!r.ok) throw new Error(`Failed to load ${path}`); return r.json(); }
const fmt = { pct:(v)=> v==null?'—':(v).toFixed(1)+'%', num:(v)=> v==null?'—':Intl.NumberFormat().format(v), dec:(v,d=3)=> v==null?'—':(+v).toFixed(d), };
function makeSVGBarChart(data, {height=220, margin=24}){
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  const w = svg.clientWidth || 600, h = height, m = margin;
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  const innerW = w - m*2, innerH = h - m*2;
  const ymax = Math.max(1, ...data.map(d=>d.value||0));
  const bw = innerW / (data.length||1);
  data.forEach((d,i)=>{
    const y = d.value||0;
    const bh = (y / ymax) * innerH;
    const rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
    rect.setAttribute('x', m + i*bw + bw*0.1);
    rect.setAttribute('y', m + innerH - bh);
    rect.setAttribute('width', bw*0.8);
    rect.setAttribute('height', bh);
    rect.setAttribute('fill', 'currentColor');
    rect.setAttribute('opacity', '0.7');
    svg.appendChild(rect);
    const tx = document.createElementNS('http://www.w3.org/2000/svg','text');
    tx.setAttribute('x', m + i*bw + bw/2); tx.setAttribute('y', h - 6);
    tx.setAttribute('font-size','10'); tx.setAttribute('text-anchor','middle');
    tx.textContent = d.label; svg.appendChild(tx);
  });
  return svg;
}
function makeSVGHist(bins){
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  const w = svg.clientWidth || 600, h = 220, m = 24;
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  const innerW = w - m*2, innerH = h - m*2;
  const ymax = Math.max(1, ...bins.map(b=>b.n||0));
  const bw = innerW / (bins.length||1);
  bins.forEach((b,i)=>{
    const bh = ((b.n||0) / ymax) * innerH;
    const rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
    rect.setAttribute('x', m + i*bw + bw*0.1);
    rect.setAttribute('y', m + innerH - bh);
    rect.setAttribute('width', bw*0.8);
    rect.setAttribute('height', bh);
    rect.setAttribute('fill', 'currentColor');
    rect.setAttribute('opacity', '0.7');
    svg.appendChild(rect);
  });
  const xt = document.createElementNS('http://www.w3.org/2000/svg','text');
  xt.setAttribute('x', w/2); xt.setAttribute('y', h - 6);
  xt.setAttribute('font-size','10'); xt.setAttribute('text-anchor','middle');
  xt.textContent = 'DAI score (0 → 1)';
  svg.appendChild(xt);
  return svg;
}
function row(parent, cells){
  const tr = document.createElement('tr');
  cells.forEach(c=>{ const td = document.createElement('td'); if (c instanceof Node) td.appendChild(c); else td.textContent = c; parent.appendChild(tr); td.appendChild(document.createTextNode('')); tr.appendChild(td); });
  parent.appendChild(tr);
}
async function main(){
  const report = await fetchJSON('report.json');
  const kpi = document.querySelector('#kpi'); kpi.innerHTML='';
  [['Nodes', report.sizes.nodes_total], ['DAI mean', report.dai_stats.overall.mean?.toFixed(3)], ['RPR %', (report.expectations.rpr_percent)?.toFixed(1)+'%'], ['Gold ver', report.bundle.dai_version]]
  .forEach(([k,v])=>{ const card = document.createElement('div'); card.className='card'; card.innerHTML = `<div class="small">${k}</div><div class="kval">${v??'—'}</div>`; kpi.appendChild(card); });
  const gates = document.querySelector('#gates'); gates.innerHTML='';
  gates.innerHTML = `<div class="card"><div class="small">Checks</div><div>${report.bundle.checks_green ? '<span class="badge ok">GREEN</span>':'<span class="badge fail">RED</span>'}</div></div>` +
                    `<div class="card"><div class="small">Schema</div><div>Silver: ${Object.entries(report.schema.silver).map(([k,v])=>k+':'+v).join(', ')||'—'} · Gold: ${Object.entries(report.schema.gold).map(([k,v])=>k+':'+v).join(', ')||'—'}</div></div>`;
  document.querySelector('#hist').appendChild(makeSVGHist(report.dai_stats.histogram||[]));
  const meanData = Object.entries(report.dai_stats.by_type||{}).map(([k,v])=>({label:k, value:v.mean}));
  document.querySelector('#meanByType').appendChild(makeSVGBarChart(meanData, {}));
  const edgeData = Object.entries(report.citations.edge_counts||{}).map(([k,v])=>({label:k, value:v}));
  if (edgeData.length) document.querySelector('#edgeMix').appendChild(makeSVGBarChart(edgeData, {}));
  const compData = (report.citations.components||[]).map((x,i)=>({label:`C${i+1}`, value:x.size}));
  if (compData.length) document.querySelector('#components').appendChild(makeSVGBarChart(compData, {}));
  const taxBody = document.querySelector('#taxonomy tbody'); taxBody.innerHTML='';
  (report.taxonomy.list_coverage||[]).forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.issue}</td><td>${r.n}</td><td>${(r.mean_dai)?.toFixed(3)}</td>`; taxBody.appendChild(tr); });
  const exBody = document.querySelector('#expectations tbody'); exBody.innerHTML='';
  (report.expectations.summary||[]).forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.table}</td><td>${r.pass}</td><td>${r.fail}</td>`; exBody.appendChild(tr); });
  const topNodes = document.querySelector('#topNodes tbody'); topNodes.innerHTML='';
  (report.citations.top_nodes||[]).forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.node_id}</td><td>${r.indegree}</td>`; topNodes.appendChild(tr); });
  const rIssues = document.querySelector('#risksIssues tbody'); rIssues.innerHTML='';
  (report.top_risks.issues_lowest_mean_dai||[]).forEach(x=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${x.issue}</td><td>${(x.mean_dai)?.toFixed(3)}</td><td>${x.n}</td>`; rIssues.appendChild(tr); });
  const del = document.querySelector('#deltas'); del.innerHTML='';
  const dd = report.deltas?.against_prev || {}; [['Nodes added', dd.nodes_added], ['Δ mean DAI', (dd.mean_dai_delta==null?'—':(dd.mean_dai_delta>=0?'+':'')+dd.mean_dai_delta.toFixed(3))]]
    .forEach(([k,v])=>{ const d = document.createElement('div'); d.className='card'; d.innerHTML = `<div class="small">${k}</div><div class="kval">${v??'—'}</div>`; del.appendChild(d); });
  const rp = report.performance?.rows_processed || {}, sd = report.performance?.stage_durations_sec || {};
  const rpDiv = document.querySelector('#rowsProcessed'); const sdDiv = document.querySelector('#stageDurations');
  const bar = (obj, tgt)=>{ const data = Object.entries(obj).map(([k,v])=>({label:k,value:v})); if (data.length) tgt.appendChild(makeSVGBarChart(data, {})); };
  bar(rp, rpDiv); bar(sd, sdDiv);
  const goldHeadBody = document.querySelector('#goldHead tbody'); goldHeadBody.innerHTML='';
  (report.raw_tabs.sample_gold_head||[]).forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.node_id}</td><td>${r.node_type}</td><td>${r.dai_score}</td><td>${r.version}</td>`; goldHeadBody.appendChild(tr); });
}
document.addEventListener('DOMContentLoaded', main);
