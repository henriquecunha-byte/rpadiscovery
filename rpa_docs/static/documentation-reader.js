/* Native document reader. Saved content is text, never executable HTML. */
(() => {
    'use strict';
    const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
    const array = value => Array.isArray(value) ? value : [];
    const objects = value => array(value).filter(item => item && typeof item === 'object' && !Array.isArray(item));
    function element(tag, className = '', value = '') {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (value !== '') node.textContent = text(value);
        return node;
    }
    function create({root, fetchJSON, isCurrent, onSilent}) {
        let key = '', job = null, saved = null, sequence = 0, loaded = false, busy = false, observer = null;
        root.classList.add('document-reader');
        function clear() {
            sequence++; key = ''; job = null; saved = null; loaded = false; busy = false;
            observer?.disconnect(); observer = null;
            root.replaceChildren(); root.removeAttribute('aria-busy');
            delete root.dataset.version;
        }
        function current(token, id) { return token === sequence && job?.id === id && isCurrent(id); }
        function state(title, description, retry = false) {
            root.replaceChildren();
            const box = element('div', 'empty-state document-state');
            box.append(element('h3', '', title), element('p', '', description));
            if (retry) {
                const button = element('button', 'button secondary', 'Tentar novamente');
                button.type = 'button'; button.onclick = () => load(true); box.append(button);
            }
            root.append(box);
        }
        function update(value, visible = true) {
            const next = JSON.stringify([value.id, value.status, value.documentation_revision, value.documentation_url]);
            if (key !== next) {
                const sameJob = job?.id === value.id;
                if (!sameJob || value.status !== 'COMPLETED') clear();
                key = next; job = value; loaded = false;
            } else job = value;
            if (value.status !== 'COMPLETED') {
                state('A documentação aparece ao concluir', ['FAILED', 'CANCELLED'].includes(value.status)
                    ? 'A análise foi interrompida. Retome com os arquivos disponíveis ou reutilize o pedido para enviar as gravações novamente.'
                    : 'O conteúdo será organizado aqui, com descrições e evidências. Você não precisará baixar um arquivo para ler.');
                return;
            }
            if (visible && !loaded) load();
        }
        async function load(force = false) {
            if (!job || job.status !== 'COMPLETED' || (loaded && !force)) return;
            loaded = true;
            const id = job.id, token = ++sequence;
            root.setAttribute('aria-busy', 'true');
            const refresh = root.querySelector('.document-refresh');
            if (refresh) { refresh.disabled = true; refresh.textContent = 'Atualizando documento…'; }
            if (!saved) state('Carregando documentação', 'Buscando o documento salvo e suas evidências.');
            try {
                const data = await fetchJSON(`/api/jobs/${encodeURIComponent(id)}/documentation`);
                if (!current(token, id)) return;
                if (saved?.version === data.version && !force) return;
                saved = data; render();
            } catch (error) {
                if (!current(token, id) || onSilent(error)) return;
                loaded = true;
                if (saved) {
                    const status = root.querySelector('.document-export-status');
                    status.textContent = 'Não foi possível atualizar a leitura. O documento anterior continua aberto. Use Atualizar documento para tentar novamente.';
                    status.hidden = false;
                } else state('Não foi possível abrir a documentação', error.message || 'Confira a conexão e tente novamente.', true);
            } finally { if (current(token, id)) {
                root.removeAttribute('aria-busy');
                const refresh = root.querySelector('.document-refresh');
                if (refresh) { refresh.disabled = false; refresh.textContent = 'Atualizar documento'; }
            } }
        }
        function render() {
            observer?.disconnect(); root.replaceChildren(); busy = false;
            const id = job.id, data = saved, doc = data.documentation || {}, prefix = `document-${id}-`;
            root.dataset.version = data.version;
            const toolbar = element('div', 'document-toolbar');
            const introduction = element('div', 'document-identity');
            introduction.append(element('p', 'eyebrow', data.profile_label || 'DOCUMENTAÇÃO'), element('h2', '', data.title || job.title), element('p', 'caption', `Público: ${data.audience || 'Equipe'}`));
            const actions = element('div', 'document-export-actions');
            const pdf = element('button', 'button primary', 'Exportar PDF'); pdf.id = 'exportDocumentPdf'; pdf.type = 'button';
            const zip = element('button', 'button secondary', 'Baixar ZIP'); zip.id = 'downloadDocumentZip'; zip.type = 'button';
            zip.disabled = !job.package_url; zip.title = job.package_url ? 'Documentos e demais arquivos disponíveis desta análise' : 'O pacote não está disponível neste ambiente.';
            actions.append(pdf, zip); toolbar.append(introduction, actions);
            const status = element('p', 'document-export-status field-message'); status.setAttribute('role', 'status'); status.hidden = true;
            const formats = element('details', 'document-formats');
            formats.append(element('summary', '', 'Formatos incluídos no ZIP'));
            const included = [...new Set(array(job.documents).filter(item => item.available).map(item => item.format))];
            if (job.report_url) included.push('HTML');
            if (array(data.evidence).some(item => item.available)) included.push('Prints');
            formats.append(element('p', 'caption', included.length ? included.join(' · ') : 'Consulte a disponibilidade dos arquivos desta análise.'));
            root.append(toolbar, status, formats);
            const layout = element('div', 'document-layout');
            const outline = element('details', 'document-outline'); outline.append(element('summary', '', 'Neste documento'));
            const nav = element('nav'); nav.setAttribute('aria-label', 'Seções do documento'); const navList = element('ol'); nav.append(navList); outline.append(nav);
            const article = element('article', 'document-content'); article.setAttribute('aria-label', `Documento ${text(data.title || job.title)}`);
            layout.append(outline, article); root.append(layout);
            const seen = new Set(), figures = new Map(objects(data.evidence).map(item => [String(item.id), item]));
            function jump(targetId) {
                const target = document.getElementById(targetId);
                if (!target || !root.contains(target)) return;
                target.focus({preventScroll:true}); target.scrollIntoView({block:'start',behavior:'instant'});
            }
            function section(name, title) {
                const block = element('section', 'document-section'); block.id = prefix + name;
                const heading = element('h3', '', title); heading.tabIndex = -1; heading.id = block.id + '-heading'; block.setAttribute('aria-labelledby', heading.id);
                block.append(heading); article.append(block);
                const link = element('a', '', title); link.href = '#' + heading.id; link.onclick = event => { event.preventDefault(); jump(heading.id); };
                const item = element('li'); item.append(link); navList.append(item);
                return block;
            }
            function paragraph(parent, value, empty = 'Não identificado nos insumos disponíveis.') { parent.append(element('p', 'document-text', text(value) || empty)); }
            function list(parent, values, empty) {
                const items = array(values).map(text).filter(Boolean);
                if (!items.length) { paragraph(parent, '', empty); return; }
                const ul = element('ul'); items.forEach(value => ul.append(element('li', '', value))); parent.append(ul);
            }
            function fields(parent, value, schema) {
                const dl = element('dl', 'document-fields');
                schema.forEach(([key, label]) => { const group = element('div'); group.append(element('dt', '', label), element('dd', '', text(value[key]) || 'Não identificado.')); dl.append(group); });
                parent.append(dl);
            }
            function evidence(parent, refs) {
                for (const ref of [...new Set(array(refs).map(String))]) {
                    const figure = figures.get(ref);
                    if (seen.has(ref)) {
                        const link = element('a', 'document-evidence-link', `Ver evidência ${ref}`);
                        link.href = '#' + prefix + 'evidence-' + ref;
                        link.onclick = event => { event.preventDefault(); jump(prefix + 'evidence-' + ref); }; parent.append(link); continue;
                    }
                    if (!figure?.available) { paragraph(parent, figure?.warning || `Evidência ${ref} indisponível. Revise a fonte.`); continue; }
                    let url;
                    try { url = new URL(figure.url, location.origin); } catch { continue; }
                    if (url.origin !== location.origin || !url.pathname.startsWith(`/api/jobs/${encodeURIComponent(id)}/evidence/`)) continue;
                    const block = element('figure', 'document-evidence'); block.id = prefix + 'evidence-' + ref; block.tabIndex = -1;
                    const image = element('img'); image.src = url.href; image.alt = text(figure.description || figure.title) || `Evidência ${ref}`; image.loading = 'lazy'; image.decoding = 'async';
                    if (Number(figure.width) > 0 && Number(figure.height) > 0) { image.width = Number(figure.width); image.height = Number(figure.height); }
                    image.addEventListener('error', () => { image.hidden = true; const warning = element('p', 'document-image-error', 'A imagem não pôde ser carregada. Atualize o documento para tentar novamente.'); block.prepend(warning); }, {once:true});
                    const caption = element('figcaption'); caption.append(element('strong', '', `Evidência ${ref} · ${text(figure.title) || 'Tela demonstrada'}`), element('span', 'caption', [text(figure.source), text(figure.timecode)].filter(Boolean).join(' · ') || 'Origem não identificada'));
                    block.append(image, caption);
                    if (figure.description) paragraph(block, figure.description);
                    if (figure.uncertainty) block.append(element('p', 'document-uncertainty', `A validar: ${text(figure.uncertainty)}`));
                    parent.append(block); seen.add(ref);
                }
            }
            paragraph(section('summary', 'Resumo executivo'), doc.executive_summary);
            paragraph(section('objective', 'Objetivo'), doc.objective);
            const scope = section('scope', 'Escopo');
            scope.append(element('h4', '', 'Incluído')); list(scope, doc.scope?.in_scope, 'Não explicitado nos insumos.');
            scope.append(element('h4', '', 'Fora do escopo')); list(scope, doc.scope?.out_of_scope, 'Não explicitado nos insumos.');
            function records(name, title, values, schema, headingKey, empty = 'Não identificado nos insumos disponíveis.') {
                const block = section(name, title), rows = objects(values);
                if (!rows.length) { paragraph(block, '', empty); return block; }
                rows.forEach(value => {
                    const item = element('div', 'document-item');
                    if (headingKey && value[headingKey]) item.append(element('h4', '', value[headingKey]));
                    fields(item, value, schema); block.append(item);
                    if (array(value.evidence_refs).length) evidence(item, value.evidence_refs);
                });
                return block;
            }
            if (data.profile === 'processo') {
                records('actors', 'Atores e responsabilidades', doc.actors, [['responsibility','Responsabilidade']], 'name');
                records('systems', 'Sistemas envolvidos', doc.systems, [['purpose','Finalidade']], 'name');
                list(section('prerequisites','Pré-requisitos'), doc.prerequisites, 'Não identificados nos insumos disponíveis.');
                records('inputs','Entradas',doc.inputs,[['source','Origem'],['required','Obrigatoriedade']],'name');
                records('outputs','Saídas',doc.outputs,[['destination','Destino']],'name');
                const flow = section('flow','Fluxo operacional');
                if (!objects(doc.process_flow).length) paragraph(flow, '', 'Nenhuma etapa foi identificada nos insumos.');
                objects(doc.process_flow).forEach((item,index) => {
                    const step = element('div', 'document-step');
                    step.append(element('span', 'document-step-number', String(item.sequence || index+1).padStart(2,'0')), element('h4', '', item.title || `Etapa ${index+1}`));
                    paragraph(step, item.description);
                    fields(step,item,[['actor','Responsável'],['system','Sistema'],['input','Entrada'],['output','Saída'],['decision_or_exception','Decisão ou exceção']]);
                    evidence(step,item.evidence_refs); flow.append(step);
                });
                const rules = section('rules','Regras de negócio');
                if (!objects(doc.business_rules).length) paragraph(rules,'','Nenhuma regra foi explicitada nos insumos.');
                objects(doc.business_rules).forEach(item=>{const block=element('div','document-item');paragraph(block,item.rule);evidence(block,item.evidence_refs);rules.append(block);});
                records('exceptions','Exceções e tratamentos',doc.exceptions,[['handling','Tratamento'],['status','Status']],'scenario','Nenhuma exceção foi explicitada.');
                records('risks','Riscos e controles',doc.risks_and_controls,[['impact','Impacto'],['control','Controle']],'risk','Nenhum risco ou controle foi identificado.');
                records('opportunities','Oportunidades de automação',doc.automation_opportunities,[['benefit','Benefício'],['dependency','Dependência']],'opportunity','Nenhuma oportunidade foi confirmada.');
            } else {
                objects(doc.sections).forEach((item,index)=>{
                    const block=section('section-'+index,text(item.title)||'Conteúdo documentado');
                    if(!objects(item.items).length) paragraph(block,'','Não foi identificado conteúdo suficiente para esta seção. Consulte as limitações.');
                    objects(item.items).forEach(value=>{const entry=element('div','document-item');if(value.title)entry.append(element('h4','',value.title));paragraph(entry,value.text);if(value.timecode)entry.append(element('p','caption',`Momento da gravação: ${text(value.timecode)}`));evidence(entry,value.evidence_refs);block.append(entry);});
                });
            }
            list(section('questions','Pontos a validar'),doc.open_questions,'Nenhum ponto adicional registrado.');
            list(section('limitations','Limitações da análise'),doc.limitations,'Nenhuma limitação adicional registrada.');
            if(data.guide){paragraph(section('guide','Guia recebido para esta análise'),data.guide);article.lastChild.append(element('p','document-uncertainty','Orientação do pedido; não equivale a um fato confirmado.'));}
            let narrow = root.clientWidth < 820; outline.open = !narrow;
            observer = new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(!width)return;const next=width<820;if(next!==narrow){narrow=next;outline.open=!next;}});observer.observe(root);
            async function download(kind) {
                if(busy || !saved) return;
                const token=sequence, version=saved.version; busy=true; pdf.disabled=true; zip.disabled=true;
                const trigger=kind==='pdf'?pdf:zip, label=trigger.textContent;trigger.textContent=kind==='pdf'?'Exportando PDF…':'Preparando ZIP…';
                status.hidden=false;status.textContent=kind==='pdf'?'Exportando o documento que está aberto. Não há nova análise de IA.':'Preparando os arquivos disponíveis desta versão.';
                try {
                    const blob=await fetchJSON(`/api/jobs/${encodeURIComponent(id)}/documentation/${kind==='pdf'?'pdf':'package'}?version=${encodeURIComponent(version)}`,{responseType:'blob'});
                    if(!current(token,id))return;
                    if(!(blob instanceof Blob) || !blob.type.includes(kind==='pdf'?'application/pdf':'application/zip'))throw new Error('O servidor não retornou um arquivo válido. Tente novamente.');
                    const objectURL=URL.createObjectURL(blob), link=element('a');link.href=objectURL;link.download=kind==='pdf'?'documentacao.pdf':'documentacao-completa.zip';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(objectURL),30000);
                    status.textContent=kind==='pdf'?'PDF exportado. A leitura continua aberta.':'Download do ZIP iniciado.';
                }catch(error){if(current(token,id)&&!onSilent(error)){status.textContent=error.message||'Não foi possível exportar. Tente novamente.';if(error.status===409 && !error.message.includes('pacote salvo'))status.textContent+=' Use Atualizar documento para carregar a versão atual.';}}
                finally{if(current(token,id)){busy=false;pdf.disabled=false;zip.disabled=!job.package_url;trigger.textContent=label;}}
            }
            pdf.onclick=()=>download('pdf'); zip.onclick=()=>download('zip');
            const refresh=element('button','text-button document-refresh','Atualizar documento');refresh.type='button';refresh.onclick=()=>{if(!busy)load(true);};root.append(refresh);
        }
        return {update,clear};
    }
    window.DiscoveryDocumentation={create};
})();
