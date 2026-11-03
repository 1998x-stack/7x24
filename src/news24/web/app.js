"use strict";
/* All upstream and model-produced strings are rendered with textContent,
   never innerHTML. Authentication tokens exist only in an input's memory. */
const state = {view:"news", offset:0, query:"", selected:null, analysis:null, event:null};
const root = document.getElementById("main");
const notice = document.getElementById("notice");
const heading = document.getElementById("heading");
const subtitle = document.getElementById("subtitle");
const pageNames = {
  news:["资讯检索","查看规范化新闻、来源版本与逐条证据"],
  events:["候选事件","按相同长引用聚合；候选不等于事实"],
  jobs:["任务监控","观察持久任务队列及接口健康"],
  quality:["质量评测","审查离线黄金集及独立验收记录"]
};
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if(cls) n.className = cls;
  if(text !== undefined && text !== null) n.textContent = String(text);
  return n;
}
function clear(node) { while(node.firstChild) node.removeChild(node.firstChild); }
function add(parent,...nodes) { for(const node of nodes) parent.append(node); return parent; }
function panel(title) { const p=el("section","panel"); if(title) p.append(el("h2",null,title)); return p; }
function badge(text,kind="") { return el("span","pill "+kind,text); }
function button(label,handler,kind="") {
  const b=el("button",kind,label); b.type="button";
  b.addEventListener("click",()=>guard(handler));return b;
}
function row(label,value) {
  const p=el("p"); add(p,el("strong",null,label+"："),document.createTextNode(String(value??"—")));return p;
}
function text(node,content) {node.textContent=String(content??"");return node;}
function showNotice(content) {
  text(notice,content);notice.hidden=false;
}
function hideNotice(){notice.hidden=true;text(notice,"");}
function guard(fn){
  Promise.resolve().then(fn).catch(e=>showNotice(e.message||"请求失败"));
}
async function fetchData(route) {
  const res=await fetch(route,{cache:"no-store",credentials:"omit"});
  const data=await res.json();
  if(!res.ok) throw Error(data.error||"数据访问失败");
  return data;
}
async function postData(route,body) {
  const token=document.getElementById("review-token").value;
  if(!token) throw Error("审核需要设置本地令牌；数据不会保存在浏览器");
  const res=await fetch(route,{
    method:"POST",cache:"no-store",credentials:"omit",
    headers:{"Content-Type":"application/json","Authorization":"Bearer "+token},
    body:JSON.stringify(body)
  });
  const data=await res.json();
  if(!res.ok) throw Error(data.error||"审核提交失败");
  return data;
}
function setView(view) {
  state.view=view;state.selected=null;state.analysis=null;state.event=null;
  clear(root);hideNotice();
  const info=pageNames[view];text(heading,info[0]);text(subtitle,info[1]);
  for(const b of document.querySelectorAll("#nav button")){
    b.classList.toggle("active",b.dataset.view===view);
    b.setAttribute("aria-current",b.dataset.view===view?"page":"false");
  }
  if(view==="news") guard(showNews);
  if(view==="events") guard(showEvents);
  if(view==="jobs") guard(showJobs);
  if(view==="quality") guard(showQuality);
}
function message(parent,content) {parent.append(el("p","empty",content));}
function titleText(content){return el("h3",null,content||"未命名新闻");}
function metaText(content){return el("div","meta",content||"");}
function labeledKpi(label,value){
  const p=panel(null);p.classList.add("kpi");
  add(p,el("small",null,label),el("strong",null,value));return p;
}
async function showNews(){
  clear(root);
  const toolbar=el("div","toolbar");const input=el("input");
  input.type="search";input.placeholder="标题或正文检索";input.value=state.query;
  input.setAttribute("aria-label","检索新闻");
  const search=()=>{state.query=input.value.trim();state.offset=0;return showNews();};
  input.addEventListener("keydown",e=>{if(e.key==="Enter")guard(search);});
  add(toolbar,input,button("搜索",search,"primary"));
  root.append(toolbar);
  const grid=el("div","columns");
  const results=panel("来源记录"),detail=panel("新闻与分析详情");
  add(grid,results,detail);root.append(grid);
  const args=new URLSearchParams({q:state.query,offset:state.offset,limit:25});
  const data=await fetchData("/api/news?"+args.toString());
  results.append(metaText("数据库匹配："+data.total+" 条 · 分页显示"));
  for(const item of data.items){
    const card=el("article","item");
    add(card,titleText(item.title||item.uid),
      el("p",null,item.excerpt||""),
      metaText([item.source,item.published_at].filter(Boolean).join(" · ")));
    card.tabIndex=0;card.setAttribute("role","button");
    const open=()=>showArticle(item.uid,detail);
    card.addEventListener("click",()=>guard(open));
    card.addEventListener("keydown",ev=>{if(ev.key==="Enter")guard(open);});
    results.append(card);
  }
  if(!data.items.length)message(results,"当前筛选条件下没有保存的新闻。");
  const pagination=el("div","mini-bar");
  if(state.offset>0) pagination.append(button("上一页",()=>{state.offset=Math.max(0,state.offset-25);return showNews();}));
  if(data.next_offset!==null)pagination.append(button("下一页",()=>{state.offset=data.next_offset;return showNews();}));
  results.append(pagination);
  if(state.selected) await showArticle(state.selected,detail);
  else message(detail,"选择左侧新闻，查看原文、模型分析及逐条证据。");
}
function sourceTextWithMark(content,start,end){
  const wrap=el("div","story");
  if(Number.isInteger(start)&&Number.isInteger(end)&&start>=0&&end<=content.length&&end>start){
    add(wrap,document.createTextNode(content.slice(0,start)),
      el("mark",null,content.slice(start,end)),
      document.createTextNode(content.slice(end)));
  } else {
    wrap.textContent=content;
  }
  return wrap;
}
function reviewForm({kind,context,version,onDone,validMatch=true}){
  const form=el("div","review-box");
  const header=el("h3",null,"人工审核 · 仅表示对存储文本的判断");
  const choice=el("select");choice.setAttribute("aria-label","审核结论");
  const choices=kind==="claim"?[
    ["NEEDS_INVESTIGATION","需要进一步核查"],
    ["SUPPORTED_BY_TEXT","原文可支持（并非事实证明）"],
    ["NOT_SUPPORTED_BY_TEXT","原文不支持"],
  ]:[
    ["NEEDS_INVESTIGATION","事件关联有待核实"],
    ["RELATED","标记为相关候选"],
    ["NOT_RELATED","并非同一事件"],
  ];
  for(const [v,name] of choices) {
    const opt=el("option",null,name);opt.value=v;
    if(!validMatch&&v==="SUPPORTED_BY_TEXT") opt.disabled=true;
    choice.append(opt);
  }
  const reason=el("textarea");reason.placeholder="请说明判断依据（8–1000 字符）";
  reason.setAttribute("aria-label","审核原因");
  const submit=button("提交审核记录",async()=>{
    if(reason.value.trim().length<8)throw Error("审核理由至少 8 个字符");
    const body={...context,expected_version:version,
      decision:choice.value,reason:reason.value.trim()};
    await postData(kind==="claim"?"/api/reviews/claim":"/api/reviews/event",body);
    showNotice("审核记录已保存；旧审核记录仍保留。");
    await onDone();
  },"primary");
  add(form,header,choice,reason,submit);
  return form;
}
async function showArticle(uid,target){
  state.selected=uid;clear(target);
  const data=await fetchData("/api/article?"+new URLSearchParams({uid}));
  add(target,titleText(data.title||data.uid),metaText(data.uid),
    row("来源",data.source),row("发布时间",data.published_at),
    row("当前修订",data.revision_hash?.slice(0,16)+"…"),
    badge(data.is_deleted?"来源已删除":"当前源记录",data.is_deleted?"bad":"good"));
  if(data.source_url){
    try{
      const url=new URL(data.source_url);
      if(url.protocol==="https:"){
        const a=el("a",null,"访问原始来源");
        a.href=url.href;a.target="_blank";a.rel="noopener noreferrer";
        target.append(a);
      }
    }catch(_err){/* Invalid source URL remains ignored, never executed. */}
  }
  target.append(el("h3",null,"保存的规范化正文"));
  target.append(sourceTextWithMark(data.content_text||""));
  const box=el("section");box.append(el("h3",null,"模型分析与来源证据"));
  target.append(box);
  const analyses=await fetchData("/api/analyses?"+new URLSearchParams({uid}));
  if(!analyses.items.length){message(box,"尚无分析。模型执行需从 CLI 显式创建任务。");return;}
  for(const item of analyses.items){
    const summary=el("div","audit");
    const current=item.revision_hash===data.revision_hash;
    add(summary,metaText(item.provider+" / "+item.model+" · "+item.prompt_version),
      badge(item.status,item.status==="REJECTED"?"bad":"warn"),
      badge(current?"当前内容修订":"历史修订，不可审核",current?"good":"bad"),
      row("情绪候选",item.sentiment||"未判定"));
    const actions=el("div","mini-bar");
    actions.append(button("查看引文与审核",async()=>{
      state.analysis=item.analysis_key;
      await showAnalysisEvidence(item,data,summary);
    }));
    summary.append(actions);
    box.append(summary);
    if(state.analysis===item.analysis_key)await showAnalysisEvidence(item,data,summary);
  }
}
async function showAnalysisEvidence(analysis,article,container){
  const prior=container.querySelector(".evidence-list");
  if(prior)prior.remove();
  const wrap=el("div","evidence-list");
  container.append(wrap);
  const result=await fetchData("/api/evidence?"+new URLSearchParams({key:analysis.analysis_key}));
  if(!result.items.length)message(wrap,"模型没有提出带引文的主张。");
  for(const claim of result.items){
    const section=el("div","review-box");
    add(section,row("候选主张",claim.statement),
      row("引用核验",claim.verdict),
      el("blockquote",null,claim.quote),
      sourceTextWithMark(article.content_text||"",claim.span_start,claim.span_end));
    const latest=result.reviews.find(r=>r.claim_index===claim.claim_index);
    if(latest) section.append(metaText(
      "最近审核："+latest.verdict+" · v"+latest.review_version+" · "+latest.reason
    ));
    if(analysis.revision_hash===article.revision_hash&&!article.is_deleted){
      section.append(reviewForm({
        kind:"claim",context:{
          analysis_key:analysis.analysis_key,claim_index:claim.claim_index,
          expected_source_revision:analysis.revision_hash,
        },
        version:latest?latest.review_version:0,
        validMatch:claim.verdict==="TEXT_MATCH_ONLY",
        onDone:()=>showAnalysisEvidence(analysis,article,container),
      }));
    }
    wrap.append(section);
  }
}
async function showEvents(){
  clear(root);
  const panelEvents=panel("相同长引用 · 保守分组");
  root.append(panelEvents);
  const data=await fetchData("/api/events?limit=100");
  if(!data.items.length)message(panelEvents,"暂无候选事件；系统不会凭新闻数量自动虚构事件。");
  const layout=el("div","columns");const events=el("div"),detail=panel("事件详情");
  add(layout,events,detail);panelEvents.append(layout);
  for(const rowdata of data.items){
    const item=el("div","item");
    add(item,titleText(rowdata.normalized_quote),
      metaText(rowdata.local_day+" · "+rowdata.distinct_articles+" 篇文章 · CANDIDATE"));
    item.tabIndex=0;item.setAttribute("role","button");
    const open=()=>showEventDetail(rowdata.event_key,detail);
    item.addEventListener("click",()=>guard(open));
    item.addEventListener("keydown",e=>{if(e.key==="Enter")guard(open);});
    events.append(item);
  }
  if(state.event)await showEventDetail(state.event,detail);
  else message(detail,"请选择候选事件。相似引用不等于独立来源证明。");
}
async function showEventDetail(key,target){
  state.event=key;clear(target);
  const info=await fetchData("/api/event?"+new URLSearchParams({key}));
  add(target,titleText(info.normalized_quote),
    badge("仅候选事件","warn"),row("本地日期",info.local_day),
    row("当前有效引用成员",info.members.length));
  for(const x of info.members){
    const member=el("div","audit");
    add(member,row("新闻",x.title||x.uid),
      metaText(x.uid+" · "+x.published_at),
      el("blockquote",null,x.quote));
    target.append(member);
  }
  if(!info.members.length){message(target,"该候选事件已无当前有效来源，不允许审核。");return;}
  const latest=info.reviews[0];
  if(latest)target.append(row("最新审核",
    "v"+latest.review_version+" · "+latest.verdict+" · "+latest.reason));
  target.append(reviewForm({
    kind:"event",context:{event_key:key},version:latest?latest.review_version:0,
    onDone:()=>showEventDetail(key,target),
  }));
}
async function showJobs(){
  clear(root);
  const health=await fetchData("/api/health");
  const counts=health.job_counts||{};
  const stats=el("div","stats");
  add(stats,labeledKpi("运行状态",health.database||"未知"),
    labeledKpi("等待执行",(counts.QUEUED||0)+(counts.RETRY_WAIT||0)),
    labeledKpi("失败任务",counts.FAILED||0));
  root.append(stats);
  const status=panel("外部来源与采集状态");
  add(status,row("最近源站探测",health.last_source_probe?.status||"未探测"),
    row("探测时间",health.last_source_probe?.checked_at||"—"),
    row("最近采集",health.last_ingestion?.status||"未采集"),
    el("p",null,"状态只反映本地历史记录；不是实时源站 SLA。"));
  root.append(status);
  const jobs=await fetchData("/api/jobs?limit=80");
  const tablePanel=panel("最近任务");
  const scroll=el("div","table-scroll");const table=el("table");
  const thead=el("thead");const tr=el("tr");
  for(const name of ["任务","类型","状态","尝试次数","更新时间"])tr.append(el("th",null,name));
  thead.append(tr);table.append(thead);
  const tbody=el("tbody");
  for(const job of jobs.items){
    const line=el("tr");
    for(const value of [job.job_key,job.kind,job.state,
      job.attempts+"/"+job.max_attempts,job.updated_at])line.append(el("td",null,value));
    tbody.append(line);
  }
  table.append(tbody);scroll.append(table);tablePanel.append(scroll);root.append(tablePanel);
  if(!jobs.items.length)message(tablePanel,"暂无任务。");
}
async function showQuality(){
  clear(root);
  const p=panel("独立黄金集评测记录");
  const data=await fetchData("/api/evaluations");
  add(p,el("p",null,"这是本地黄金集的精确匹配结果，不衡量事实真伪或模型投资准确率。"));
  root.append(p);
  if(!data.items.length){message(p,"尚无评测记录。请运行 news24 evaluate evidence。");return;}
  for(const record of data.items){
    const item=el("div","item");
    add(item,titleText(record.algorithm),
      row("通过",record.passed_cases+" / "+record.total_cases),
      row("数据集 SHA-256",record.dataset_sha256),
      metaText(record.evaluated_at));
    p.append(item);
  }
}
document.querySelectorAll("#nav button").forEach(b=>{
  b.addEventListener("click",()=>setView(b.dataset.view));
});
setView("news");
