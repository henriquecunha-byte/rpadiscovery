(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
    const active = status => ['QUEUED', 'RUNNING', 'CANCEL_REQUESTED'].includes(status);
    const labels = { QUEUED: 'Na fila', RUNNING: 'Em análise', CANCEL_REQUESTED: 'Cancelando', COMPLETED: 'Concluído', FAILED: 'Com falha', CANCELLED: 'Cancelado' };
    const detailLabels = { operacional: 'Operacional', detalhado: 'Detalhado', resumido: 'Resumido' };
    const videoPattern = /\.(mp4|mov|mkv|webm|avi|m4v|zip)$/i;
    const draftKey = 'btime.discovery.draft.v1';
    const state = { view: 'new', jobId: null, job: null, jobs: [], files: [], driveFiles: [], drivePicked: new Map(), step: 1, submitting: false, selecting: false, jobAction: false, detailRequest: 0, driveRequest: 0, detailLoading: false, jobsLoading: false, driveConnected: false, driveConfigured: false, health: null, folderStack: [{ id: 'root', name: 'Meu Drive' }] };
    const icons = {
        plus: '<path d="M12 5v14M5 12h14"/>', close: '<path d="m6 6 12 12M18 6 6 18"/>', upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 16v4h16v-4"/>', download: '<path d="M12 4v12m-5-5 5 5 5-5M4 17v3h16v-3"/>', folder: '<path d="M3 7V5h6l2 2h10v13H3Z"/>', layers: '<path d="m12 3 10 5-10 5L2 8Zm-10 9 10 5 10-5M2 16l10 5 10-5"/>', settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>', help: '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>', drive: '<path d="m9 3 6 0 7 12-3 6H5l-3-6Zm0 0 7 12M2 15h20M5 21l7-12"/>', spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>', package: '<path d="m3 7 9-5 9 5v10l-9 5-9-5Zm0 0 9 5 9-5M12 12v10M7.5 4.5l9 5"/>', search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>', refresh: '<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>', trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>', copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H4v13h4"/>', video: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 5 3-5 3Z"/>', document: '<path d="M5 3h10l4 4v14H5ZM14 3v5h5M8 12h8M8 16h8"/>', check: '<path d="m5 12 4 4L19 6"/>'
    };
    const icon = name => `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.document}</svg>`;
    document.querySelectorAll('[data-icon]').forEach(element => { element.innerHTML = icon(element.dataset.icon); });
    const storage = { get(key) {
            try {
                return localStorage.getItem(key);
            }
            catch {
                return null;
            }
        }, set(key, value) {
            try {
                localStorage.setItem(key, value);
                return true;
            }
            catch {
                return false;
            }
        }, remove(key) {
            try {
                localStorage.removeItem(key);
            }
            catch { }
        } };
    function message(id, text = '') { $(id).textContent = text; $(id).hidden = !text; }
    let toastTimer;
    function toast(text, error = false) { clearTimeout(toastTimer); $('toast').textContent = text; $('toast').classList.toggle('error', error); $('toast').hidden = false; toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 8000 : 5000); }
    function safeUrl(value, external = false) {
        try {
            const url = new URL(value, location.origin);
            if (!value || url.username || url.password)
                return '';
            return external ? (url.protocol === 'https:' && /(^|\.)google\.com$/.test(url.hostname) ? url.href : '') : (url.origin === location.origin && url.pathname.startsWith('/api/') ? url.href : '');
        }
        catch {
            return '';
        }
    }
    function duration(value) {
        if (value === null || value === undefined || !Number.isFinite(Number(value)))
            return '—';
        const n = Math.max(0, Math.round(Number(value)));
        return n >= 3600 ? `${Math.floor(n / 3600)}h ${String(Math.floor(n % 3600 / 60)).padStart(2, '0')}m` : `${Math.floor(n / 60)}m ${String(n % 60).padStart(2, '0')}s`;
    }
    function timecode(value) { const n = Math.max(0, Math.round(Number(value) || 0)); return [Math.floor(n / 3600), Math.floor(n % 3600 / 60), n % 60].map(part => String(part).padStart(2, '0')).join(':'); }
    function bytes(value) { const n = Number(value); return !Number.isFinite(n) || n < 1 ? 'Tamanho não informado' : n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(2)} GB` : `${(n / 1024 ** 2).toFixed(1)} MB`; }
    function date(value) { const parsed = new Date(value); return Number.isFinite(parsed.getTime()) ? parsed.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : 'Data não informada'; }
    function resultOf(job) {
        try {
            const value = typeof job.result_json === 'string' ? JSON.parse(job.result_json) : job.result_json;
            return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
        }
        catch {
            return {};
        }
    }
    function errorText(body, status) {
        if (Array.isArray(body?.detail))
            return body.detail.map(item => `${({ title: 'Nome do processo', process_context: 'Guia de análise', api_budget_usd: 'Orçamento', detail_level: 'Nível de detalhe' }[item.loc?.at(-1)] || 'Campo')}: ${item.msg}`).join(' · ');
        return typeof body?.detail === 'string' ? body.detail : status === 413 ? 'Os arquivos ultrapassam o limite de envio deste ambiente.' : status === 404 ? 'Este trabalho não foi encontrado.' : 'Não foi possível concluir. Tente novamente.';
    }
    async function api(path, options = {}) {
        let response;
        try {
            response = await fetch(path, { ...options, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers } });
        }
        catch {
            throw new Error('Não foi possível conectar ao aplicativo. Verifique se o servidor está ativo e tente novamente.');
        }
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(errorText(body, response.status));
            error.status = response.status;
            throw error;
        }
        return body;
    }
    const dialogOpeners = new WeakMap();
    function returnFocus(opener) {
        let target = opener;
        if (!target?.isConnected && opener?.dataset.job && opener?.dataset.jobAction)
            target = document.querySelector(`[data-job="${CSS.escape(opener.dataset.job)}"][data-job-action="${CSS.escape(opener.dataset.jobAction)}"]`);
        if (target?.isConnected && !target.disabled)
            target.focus();
    }
    let lastControl = null;
    document.addEventListener('click', event => {
        const control = event.target.closest('button,a,input');
        if (control)
            lastControl = control;
    }, true);
    function openDialog(dialog) {
        if (dialog.open)
            return;
        const focused = document.activeElement;
        dialogOpeners.set(dialog, focused && focused !== document.body && !focused.disabled ? focused : lastControl);
        dialog.classList.remove('is-closing');
        dialog.showModal();
    }
    function closeDialog(dialog) {
        if (!dialog.open || dialog.classList.contains('is-closing'))
            return Promise.resolve();
        dialog.classList.add('is-closing');
        return new Promise(resolve => setTimeout(() => {
            dialog.close();
            dialog.classList.remove('is-closing');
            const opener = dialogOpeners.get(dialog);
            returnFocus(opener);
            resolve();
        }, matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 160));
    }
    let confirmResolve = null;
    function ask(title, text, action = 'Confirmar', danger = false) {
        if (confirmResolve)
            return Promise.resolve(false);
        $('confirmTitle').textContent = title;
        $('confirmMessage').textContent = text;
        $('acceptConfirm').textContent = action;
        $('acceptConfirm').classList.toggle('danger', danger);
        openDialog($('confirmDialog'));
        $('rejectConfirm').focus();
        return new Promise(resolve => { confirmResolve = resolve; });
    }
    async function answerConfirm(answer) {
        const resolve = confirmResolve;
        if (!resolve)
            return;
        const opener = dialogOpeners.get($('confirmDialog'));
        confirmResolve = null;
        await closeDialog($('confirmDialog'));
        resolve(answer);
        queueMicrotask(() => {
            if (!answer)
                returnFocus(opener);
        });
    }
    $('acceptConfirm').onclick = () => answerConfirm(true);
    $('rejectConfirm').onclick = $('dismissConfirm').onclick = () => answerConfirm(false);
    document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('cancel', event => { event.preventDefault(); dialog.id === 'confirmDialog' ? answerConfirm(false) : closeDialog(dialog); }));
    $('helpButton').onclick = () => openDialog($('helpDialog'));
    $('closeHelp').onclick = $('startFromHelp').onclick = () => closeDialog($('helpDialog'));
    function fields() { return { title: $('title').value, process_context: $('context').value, audience: $('audience').value, detail_level: $('detail').value, api_budget_usd: $('budget').value }; }
    function applyFields(value) { $('title').value = String(value.title || '').slice(0, 120); $('context').value = String(value.process_context || '').slice(0, 8000); $('audience').value = String(value.audience || 'Equipe de RPA').slice(0, 160); $('detail').value = detailLabels[value.detail_level] ? value.detail_level : 'operacional'; const budget = Number(value.api_budget_usd); $('budget').value = Number.isFinite(budget) && budget >= 0.1 && budget <= 50 ? budget : 1; $('contextCount').textContent = `${$('context').value.length.toLocaleString('pt-BR')} / 8.000`; }
    function saveDraft() { $('contextCount').textContent = `${$('context').value.length.toLocaleString('pt-BR')} / 8.000`; $('draftStatus').textContent = storage.set(draftKey, JSON.stringify(fields())) ? 'Rascunho salvo neste navegador' : 'Rascunho nesta sessão'; }
    try {
        const draft = JSON.parse(storage.get(draftKey) || 'null');
        if (draft && typeof draft === 'object') {
            applyFields(draft);
            $('draftStatus').textContent = 'Rascunho recuperado';
        }
    }
    catch {
        storage.remove(draftKey);
    }
    ['title', 'context', 'audience', 'detail', 'budget'].forEach(id => $(id).addEventListener('input', () => {
        saveDraft();
        if (['title', 'context', 'budget'].includes(id)) {
            $(id).removeAttribute('aria-invalid');
            message(`${id}Error`);
        }
    }));
    const fileName = file => file._relativePath || file.webkitRelativePath || file.name;
    const fileKey = file => `${fileName(file)}|${file.size}|${file.lastModified || 0}`;
    function sources() { return [...state.files.map(file => ({ name: fileName(file), size: file.size, source: 'local' })), ...state.driveFiles.map(file => ({ ...file, source: 'drive' }))]; }
    function renderFiles() {
        const items = sources();
        $('fileStackSection').hidden = !items.length;
        $('dropzone').classList.toggle('ready', !!items.length);
        $('selection').textContent = `${items.length} arquivo${items.length === 1 ? '' : 's'} na pilha · ${bytes(items.reduce((sum, item) => sum + (Number(item.size) || 0), 0))}`;
        $('fileStack').innerHTML = items.map((item, index) => `<div class="file-row file-stack-item"><span class="file-icon">${icon(/\.zip$/i.test(item.name) ? 'package' : 'video')}</span><div class="file-info"><strong>${escape(item.name)}</strong><small>${item.source === 'drive' ? 'Google Drive' : 'Arquivo local'} · ${escape(bytes(item.size))}</small></div><button type="button" class="icon-button" data-remove="${index}" aria-label="Remover ${escape(item.name)}">${icon('close')}</button></div>`).join('');
        $('fileStack').querySelectorAll('[data-remove]').forEach(button => {
            button.disabled = state.submitting;
            button.onclick = () => {
                if (state.submitting)
                    return;
                const index = Number(button.dataset.remove);
                if (index < state.files.length)
                    state.files.splice(index, 1);
                else
                    state.driveFiles.splice(index - state.files.length, 1);
                renderFiles();
            };
        });
    }
    async function selectFiles(input) {
        if (state.submitting || state.selecting)
            return;
        state.selecting = true;
        try {
            const all = Array.from(input), compatible = all.filter(file => videoPattern.test(file.name) && file.size > 0);
            if (!compatible.length) {
                message('fileNotice', 'Nenhum vídeo ou ZIP válido encontrado. Arquivos vazios e formatos não suportados não são adicionados.');
                return;
            }
            if (state.driveFiles.length && !await ask('Trocar a origem dos arquivos?', 'As gravações escolhidas no Google Drive serão substituídas pelos arquivos do computador.', 'Usar arquivos locais'))
                return;
            if (state.driveFiles.length) {
                state.driveFiles = [];
                state.drivePicked.clear();
            }
            const keys = new Set(state.files.map(fileKey));
            let duplicates = 0, excess = 0;
            for (const file of compatible) {
                const key = fileKey(file);
                if (keys.has(key)) {
                    duplicates++;
                    continue;
                }
                if (state.files.length >= 100) {
                    excess++;
                    continue;
                }
                keys.add(key);
                state.files.push(file);
            }
            const notices = [];
            if (all.length - compatible.length)
                notices.push(`${all.length - compatible.length} arquivo(s) vazio(s) ou não compatível(is) ignorado(s).`);
            if (duplicates)
                notices.push(`${duplicates} repetido(s) ignorado(s).`);
            if (excess)
                notices.push('O limite é de 100 arquivos por pedido. Os demais não foram adicionados.');
            message('fileNotice', notices.join(' '));
            renderFiles();
        }
        finally {
            state.selecting = false;
        }
    }
    async function droppedFiles(transfer) {
        const entries = Array.from(transfer.items || []).map(item => item.webkitGetAsEntry?.()).filter(Boolean);
        if (!entries.length)
            return Array.from(transfer.files || []);
        const collected = [];
        let visited = 0;
        async function walk(entry, prefix = '') {
            if (collected.length > 100 || visited++ > 5000)
                return;
            if (entry.isFile) {
                const file = await new Promise(resolve => entry.file(resolve, () => resolve(null)));
                if (file && videoPattern.test(file.name)) {
                    file._relativePath = prefix + file.name;
                    collected.push(file);
                }
                return;
            }
            if (entry.isDirectory) {
                const reader = entry.createReader();
                while (collected.length <= 100 && visited <= 5000) {
                    const batch = await new Promise(resolve => reader.readEntries(resolve, () => resolve([])));
                    if (!batch.length)
                        break;
                    for (const child of batch)
                        await walk(child, `${prefix}${entry.name}/`);
                }
            }
        }
        for (const entry of entries)
            await walk(entry);
        return collected;
    }
    $('chooseVideo').onclick = () => $('videoInput').click();
    $('chooseFolder').onclick = () => $('folderInput').click();
    ['videoInput', 'folderInput'].forEach(id => $(id).addEventListener('change', event => { selectFiles(event.target.files); event.target.value = ''; }));
    ['dragenter', 'dragover'].forEach(name => $('dropzone').addEventListener(name, event => {
        event.preventDefault();
        if (!state.submitting)
            $('dropzone').classList.add('dragging');
    }));
    ['dragleave', 'drop'].forEach(name => $('dropzone').addEventListener(name, event => { event.preventDefault(); $('dropzone').classList.remove('dragging'); }));
    $('dropzone').addEventListener('drop', async (event) => {
        if (state.submitting)
            return;
        try {
            await selectFiles(await droppedFiles(event.dataTransfer));
        }
        catch {
            message('fileNotice', 'Não foi possível ler esta pasta. Use Selecionar pasta para tentar novamente.');
        }
    });
    $('clearFiles').onclick = async () => {
        if (state.submitting || !await ask('Limpar a seleção?', 'Os arquivos sairão deste pedido. Os originais continuam no computador ou Drive.', 'Limpar seleção'))
            return;
        state.files = [];
        state.driveFiles = [];
        state.drivePicked.clear();
        renderFiles();
        message('fileNotice');
    };
    function validateSources() {
        if (sources().length)
            return true;
        message('fileNotice', 'Adicione pelo menos um vídeo ou ZIP para continuar.');
        setStep(1, false);
        $('chooseVideo').focus();
        return false;
    }
    function validateContext() {
        const title = $('title').value.trim(), context = $('context').value.trim();
        message('titleError', title.length < 2 ? 'Informe um nome de processo com pelo menos 2 caracteres.' : '');
        message('contextError', !context ? 'Descreva o assunto que deve permanecer nos cortes e na documentação.' : '');
        $('title').setAttribute('aria-invalid', String(title.length < 2));
        $('context').setAttribute('aria-invalid', String(!context));
        if (title.length < 2 || !context) {
            setStep(2, false);
            $(title.length < 2 ? 'title' : 'context').focus();
            return false;
        }
        return true;
    }
    function setStep(step, validate = true) {
        if (state.submitting)
            return;
        if (validate && step > 1 && !validateSources())
            return;
        if (validate && step > 2 && !validateContext())
            return;
        state.step = step;
        [1, 2, 3].forEach(n => { $(`step${n}`).hidden = n !== step; });
        document.querySelectorAll('.stepper [data-step]').forEach(button => {
            if (Number(button.dataset.step) === step)
                button.setAttribute('aria-current', 'step');
            else
                button.removeAttribute('aria-current');
            button.classList.toggle('complete', Number(button.dataset.step) < step);
        });
        $('previousStep').hidden = step === 1;
        $('nextStep').hidden = step === 3;
        $('submitJob').hidden = step !== 3;
        $('stepCaption').textContent = `Etapa ${step} de 3`;
        if (step === 3) {
            $('reviewTitle').textContent = $('title').value.trim();
            $('reviewContext').textContent = $('context').value.trim();
            $('reviewSources').textContent = `${sources().length} arquivo(s) · ${state.driveFiles.length ? 'Google Drive' : 'Computador'}`;
            $('reviewDetail').textContent = `${detailLabels[$('detail').value]} · ${$('audience').value.trim() || 'Equipe de RPA'}`;
        }
    }
    document.querySelectorAll('[data-step]').forEach(button => button.onclick = () => setStep(Number(button.dataset.step)));
    $('nextStep').onclick = () => setStep(state.step + 1);
    $('previousStep').onclick = () => setStep(state.step - 1);
    $('suggestPrompt').onclick = async () => {
        if (state.submitting)
            return;
        const button = $('suggestPrompt'), before = JSON.stringify(fields()), label = button.innerHTML;
        button.disabled = true;
        button.textContent = 'Preparando sugestão…';
        $('promptHint').textContent = 'A sugestão pode usar a API configurada e gerar consumo. Revise o resultado antes de iniciar.';
        try {
            const result = await api('/api/prompt/suggest', { method: 'POST', body: JSON.stringify({ ...fields(), sources: sources().map(item => item.name) }) });
            if (typeof result.prompt !== 'string' || !result.prompt.trim())
                throw new Error('Não recebemos uma sugestão utilizável. Continue com seu próprio guia.');
            if (JSON.stringify(fields()) !== before && !await ask('Aplicar a sugestão recebida?', 'Você editou o pedido enquanto a sugestão era preparada. Aplicar substituirá o guia que está no campo.', 'Aplicar sugestão'))
                return;
            $('context').value = result.prompt.slice(0, 8000);
            saveDraft();
            $('context').focus();
            $('promptHint').textContent = result.generated ? 'Sugestão gerada. Confira se o assunto, as regras e as exclusões representam o seu pedido.' : `Modelo de guia preparado localmente. ${result.warning || 'A sugestão pela API não estava disponível.'}`;
            toast(result.generated ? 'Sugestão aplicada. Revise o guia antes de enviar.' : 'Guia-base local aplicado; personalize o assunto.');
        }
        catch (error) {
            $('promptHint').textContent = error.message;
            toast(error.message, true);
        }
        finally {
            button.disabled = state.submitting;
            button.innerHTML = label;
        }
    };
    function upload(data) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/jobs/upload');
            xhr.responseType = 'json';
            xhr.upload.onprogress = event => {
                if (event.lengthComputable) {
                    const percent = Math.min(100, Math.round(event.loaded / event.total * 100));
                    $('uploadPercent').textContent = `${percent}%`;
                    $('uploadBar').style.width = `${percent}%`;
                    $('uploadLabel').textContent = percent === 100 ? 'Arquivos enviados. Preparando o pedido…' : 'Enviando arquivos…';
                }
            };
            xhr.onload = () => { const body = xhr.response || {}; xhr.status >= 200 && xhr.status < 300 ? resolve(body) : reject(new Error(errorText(body, xhr.status))); };
            xhr.onerror = () => reject(new Error('O envio perdeu a conexão. A seleção continua aqui para você tentar novamente.'));
            xhr.onabort = () => reject(new Error('Envio interrompido. Seus campos e arquivos continuam selecionados.'));
            xhr.send(data);
        });
    }
    $('form').onsubmit = async (event) => {
        event.preventDefault();
        if (state.submitting)
            return;
        message('error');
        if (!validateSources() || !validateContext())
            return;
        const budget = Number($('budget').value);
        if (!$('budget').value || !Number.isFinite(budget) || budget < 0.1 || budget > 50) {
            setStep(3, false);
            message('budgetError', 'Informe um valor de US$ 0,10 a US$ 50.');
            $('budget').setAttribute('aria-invalid', 'true');
            $('budget').focus();
            return;
        }
        if (!$('approved').checked) {
            setStep(3, false);
            message('error', 'Autorize o processamento com IA para iniciar esta análise.');
            $('approved').focus();
            return;
        }
        setStep(3, false);
        state.submitting = true;
        const controls = Array.from($('form').querySelectorAll('button,input,select,textarea')).map(element => [element, element.disabled]);
        controls.forEach(([element]) => { element.disabled = true; });
        $('uploadStatus').hidden = false;
        $('uploadBar').style.width = '0%';
        $('uploadPercent').textContent = state.driveFiles.length ? 'No Drive' : '0%';
        $('uploadLabel').textContent = state.driveFiles.length ? 'Transferindo as gravações do Google Drive…' : 'Enviando arquivos…';
        $('submitJob').textContent = 'Enviando pedido…';
        try {
            const payload = { ...fields(), title: $('title').value.trim(), process_context: $('context').value.trim(), audience: $('audience').value.trim() || 'Equipe de RPA', api_approved: true, api_budget_usd: budget };
            let job;
            if (state.driveFiles.length) {
                job = await api('/api/jobs/drive-import', { method: 'POST', body: JSON.stringify({ ...payload, file_ids: state.driveFiles.map(file => file.id) }) });
            }
            else {
                const data = new FormData();
                Object.entries(payload).forEach(([key, value]) => data.append(key, String(value)));
                state.files.forEach(file => data.append('files', file, fileName(file)));
                job = await upload(data);
            }
            if (!job?.id)
                throw new Error('O servidor não confirmou o pedido. Verifique Minhas análises antes de reenviar.');
            state.files = [];
            state.driveFiles = [];
            state.drivePicked.clear();
            $('approved').checked = false;
            renderFiles();
            saveDraft();
            state.jobs = [job, ...state.jobs.filter(item => item.id !== job.id)];
            renderHistory();
            navigate(`job=${encodeURIComponent(job.id)}`);
            toast('Pedido recebido. Você já pode acompanhar a análise.');
            loadJobs(true);
        }
        catch (error) {
            message('error', error.message);
            toast(error.message, true);
        }
        finally {
            state.submitting = false;
            controls.forEach(([element, disabled]) => { element.disabled = disabled; });
            $('submitJob').textContent = 'Iniciar análise →';
            $('uploadStatus').hidden = true;
            renderFiles();
        }
    };
    window.addEventListener('beforeunload', event => {
        if (state.submitting) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
    function renderDriveSelection() { $('driveSelection').textContent = state.drivePicked.size ? `${state.drivePicked.size} arquivo(s) escolhido(s)` : 'Nenhum arquivo escolhido'; $('confirmDrive').disabled = !state.drivePicked.size; }
    async function loadDriveFolder() {
        const folder = state.folderStack.at(-1), sequence = ++state.driveRequest;
        $('driveLocation').textContent = state.folderStack.map(item => item.name).join(' / ');
        $('driveBack').disabled = state.folderStack.length === 1;
        $('driveFiles').innerHTML = '<div class="empty-state"><p>Buscando gravações nesta pasta…</p></div>';
        try {
            const files = await api(`/api/drive/files?folder_id=${encodeURIComponent(folder.id)}`);
            if (sequence !== state.driveRequest)
                return;
            if (!Array.isArray(files))
                throw new Error('Não foi possível ler os arquivos desta pasta.');
            if (!files.length) {
                $('driveFiles').innerHTML = '<div class="empty-state"><h3>Esta pasta está vazia</h3><p>Nenhum vídeo ou ZIP disponível aqui.</p></div>';
                return;
            }
            $('driveFiles').innerHTML = files.map((file, index) => { const isFolder = file.mimeType === 'application/vnd.google-apps.folder'; return `<button type="button" class="drive-file${state.drivePicked.has(file.id) ? ' selected' : ''}" data-file-index="${index}"${isFolder ? '' : ` aria-pressed="${state.drivePicked.has(file.id)}"`}><span class="file-icon">${icon(isFolder ? 'folder' : /\.zip$/i.test(file.name) ? 'package' : 'video')}</span><span class="file-info"><strong>${escape(file.name)}</strong><small>${isFolder ? 'Pasta' : escape(bytes(file.size))}</small></span><span class="drive-file-action">${isFolder ? 'Abrir →' : state.drivePicked.has(file.id) ? 'Selecionado' : 'Selecionar'}</span></button>`; }).join('');
            $('driveFiles').querySelectorAll('[data-file-index]').forEach(button => {
                button.onclick = () => {
                    const file = files[Number(button.dataset.fileIndex)];
                    if (file.mimeType === 'application/vnd.google-apps.folder') {
                        state.folderStack.push({ id: file.id, name: file.name });
                        loadDriveFolder();
                        return;
                    }
                    if (state.drivePicked.has(file.id))
                        state.drivePicked.delete(file.id);
                    else {
                        if (state.drivePicked.size >= 100) {
                            toast('O limite é de 100 arquivos por pedido.', true);
                            return;
                        }
                        if (file.size !== undefined && Number(file.size) === 0) {
                            toast('Este arquivo está vazio e não pode ser analisado.', true);
                            return;
                        }
                        state.drivePicked.set(file.id, file);
                    }
                    button.classList.toggle('selected', state.drivePicked.has(file.id));
                    button.setAttribute('aria-pressed', String(state.drivePicked.has(file.id)));
                    button.querySelector('.drive-file-action').textContent = state.drivePicked.has(file.id) ? 'Selecionado' : 'Selecionar';
                    renderDriveSelection();
                };
            });
        }
        catch (error) {
            if (sequence === state.driveRequest)
                $('driveFiles').innerHTML = `<div class="empty-state"><h3>Não foi possível abrir a pasta</h3><p>${escape(error.message)}</p><button type="button" class="button secondary" id="retryDriveFolder">Tentar novamente</button></div>`;
            $('retryDriveFolder')?.addEventListener('click', loadDriveFolder);
        }
    }
    async function openDrive() {
        if (state.submitting)
            return;
        if (!state.driveConnected) {
            navigate('settings');
            toast(state.driveConfigured ? 'Conecte sua conta Google para escolher as gravações.' : 'O cliente OAuth precisa ser configurado neste ambiente antes de conectar o Drive.');
            return;
        }
        state.drivePicked = new Map(state.driveFiles.map(file => [file.id, file]));
        state.folderStack = [{ id: 'root', name: 'Meu Drive' }];
        renderDriveSelection();
        openDialog($('driveModal'));
        loadDriveFolder();
    }
    $('chooseDrive').onclick = openDrive;
    $('openDriveFromSettings').onclick = () => { navigate('new'); setStep(1, false); openDrive(); };
    $('closeDrive').onclick = () => closeDialog($('driveModal'));
    $('driveBack').onclick = () => {
        if (state.folderStack.length > 1) {
            state.folderStack.pop();
            loadDriveFolder();
        }
    };
    $('confirmDrive').onclick = async () => {
        if (!state.drivePicked.size || state.selecting)
            return;
        state.selecting = true;
        try {
            if (state.files.length && !await ask('Trocar a origem dos arquivos?', 'Os arquivos locais deste pedido serão substituídos pelas gravações escolhidas no Google Drive.', 'Usar Google Drive'))
                return;
            state.files = [];
            state.driveFiles = Array.from(state.drivePicked.values());
            renderFiles();
            message('fileNotice');
            await closeDialog($('driveModal'));
        }
        finally {
            state.selecting = false;
        }
    };
    async function loadDrive() {
        try {
            const data = await api('/api/drive/status');
            state.driveConnected = !!data.connected;
            state.driveConfigured = !!data.configured;
            $('driveBadge').textContent = data.connected ? 'Conectado' : data.configured ? 'Conectar conta' : 'Configurar';
            $('driveBadge').className = `badge ${data.connected ? 'completed' : 'queued'}`;
            $('driveStatus').textContent = data.connected ? 'Sua conta está conectada. Escolha gravações e envie as entregas quando estiverem prontas.' : data.error || (data.configured ? 'A integração está configurada. Conecte uma conta Google para começar.' : 'Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no ambiente do aplicativo para habilitar a conexão corporativa.');
            $('connectDrive').hidden = !data.configured || data.connected;
            $('openDriveFromSettings').hidden = !data.connected;
            if (data.default_folder_id && !$('driveFolder').value)
                $('driveFolder').value = data.default_folder_id;
            if (state.job)
                syncJobActions(state.job);
        }
        catch (error) {
            state.driveConnected = false;
            $('driveBadge').textContent = 'Indisponível';
            $('driveStatus').textContent = error.message;
            $('connectDrive').hidden = true;
            $('openDriveFromSettings').hidden = true;
        }
    }
    $('driveFolder').value = storage.get('btime.discovery.drive-folder') || '';
    $('driveFolder').addEventListener('input', () => storage.set('btime.discovery.drive-folder', $('driveFolder').value));
    async function checkHealth() {
        $('checkHealth').disabled = true;
        try {
            const data = await api('/api/health');
            state.health = data;
            const ready = data.worker && data.ffmpeg && data.ffprobe && data.api_configured;
            $('healthLabel').textContent = ready ? 'Pronto para analisar' : 'Configuração pendente';
            $('health').dataset.state = ready ? 'ready' : 'warning';
            $('connectionNotice').hidden = true;
            $('systemChecks').innerHTML = [['Fila de processamento', data.worker, 'Worker em execução', 'O processamento não está ativo. Reinicie o aplicativo.'], ['Processamento de vídeo', data.ffmpeg && data.ffprobe, 'FFmpeg e FFprobe disponíveis', 'Instale ou configure FFmpeg e FFprobe no ambiente.'], ['Análise com IA', data.api_configured, 'Chave configurada no servidor', 'Configure a chave da API no servidor para iniciar.']].map(([title, ok, good, bad]) => `<div class="system-check ${ok ? 'good' : 'warning'}"><span class="check-indicator ${ok ? 'ready' : 'missing'}">${icon(ok ? 'check' : 'info')}</span><div><strong>${escape(title)}</strong><p>${escape(ok ? good : bad)}</p></div></div>`).join('');
        }
        catch {
            state.health = null;
            $('healthLabel').textContent = 'Sem conexão';
            $('health').dataset.state = 'offline';
            $('connectionNotice').hidden = false;
            $('systemChecks').innerHTML = '<div class="notice error">Não foi possível conectar ao servidor local. Confirme se o aplicativo está em execução.</div>';
        }
        finally {
            $('checkHealth').disabled = false;
        }
    }
    $('checkHealth').onclick = () => Promise.allSettled([checkHealth(), loadDrive()]);
    $('health').onclick = () => { navigate('settings'); checkHealth(); };
    function badge(status) { const known = Object.hasOwn(labels, status) ? status : 'QUEUED'; return `<span class="badge ${known.toLowerCase()}">${labels[known]}</span>`; }
    function renderHistory() {
        const jobs = state.jobs, query = $('searchJobs').value.trim().toLocaleLowerCase('pt-BR'), filter = $('statusFilter').value;
        const filtered = jobs.filter(job => (filter === 'all' || (filter === 'active' ? active(job.status) : job.status === filter)) && `${job.title} ${job.process_context || ''}`.toLocaleLowerCase('pt-BR').includes(query));
        const counts = [['Total de análises', jobs.length], ['Em andamento', jobs.filter(job => active(job.status)).length], ['Entregas disponíveis', jobs.filter(job => job.status === 'COMPLETED' && !job.delivery_missing).length], ['Precisam de atenção', jobs.filter(job => job.status === 'FAILED' || job.delivery_missing).length]];
        $('historyStats').innerHTML = counts.map(([label, count]) => `<div class="stat-card"><span>${label}</span><strong>${count}</strong></div>`).join('');
        $('navCount').textContent = jobs.length;
        $('jobCount').textContent = `${filtered.length} de ${jobs.length} análise(s)`;
        $('clearQueue').disabled = state.jobAction || !jobs.some(job => ['FAILED', 'CANCELLED'].includes(job.status));
        const signature = JSON.stringify([query, filter, filtered.map(job => [job.id, job.title, job.status, job.stage, job.progress, job.updated_at, job.can_retry, job.delivery_missing]), state.jobAction]);
        if ($('jobs').dataset.signature !== signature) {
            $('jobs').dataset.signature = signature;
            $('jobs').innerHTML = filtered.length ? filtered.map(job => `<article class="job-card job" data-status="${escape(job.status.toLowerCase())}"><a class="job-main" href="#job=${encodeURIComponent(job.id)}"><div class="job-heading"><h3>${escape(job.title)}</h3>${badge(job.status)}</div><p>${escape((job.delivery_missing ? 'Arquivos da entrega ausentes neste ambiente' : job.stage) || labels[job.status] || 'Aguardando')}</p><div class="job-meta"><span>${date(job.created_at)}</span><span>${escape(detailLabels[job.detail_level] || 'Operacional')}</span>${job.operation === 'rebuild' ? '<span>Revisão</span>' : ''}</div><div class="job-progress progress" aria-hidden="true"><i style="width:${Math.max(0, Math.min(100, Number(job.progress) || 0))}%"></i></div></a><div class="job-actions"><a class="text-button" href="#job=${encodeURIComponent(job.id)}">Ver análise →</a>${['QUEUED', 'RUNNING'].includes(job.status) ? `<button class="text-button danger" data-job-action="cancel" data-job="${escape(job.id)}"${state.jobAction ? ' disabled' : ''}>Cancelar</button>` : ''}${['FAILED', 'CANCELLED'].includes(job.status) ? `<button class="button secondary" data-job-action="retry" data-job="${escape(job.id)}"${state.jobAction || job.can_retry === false ? ' disabled' : ''} title="${escape(job.can_retry === false ? job.retry_unavailable_reason || 'Os arquivos não estão disponíveis.' : '')}">Retomar</button>${job.can_retry === false ? '<span class="caption">Arquivos indisponíveis</span>' : ''}` : ''}</div></article>`).join('') : `<div class="empty-state"><span class="empty-icon">${icon(query || filter !== 'all' ? 'search' : 'layers')}</span><h3>${query || filter !== 'all' ? 'Nenhuma análise encontrada' : 'Seu próximo processo começa aqui'}</h3><p>${query || filter !== 'all' ? 'Experimente outra busca ou remova o filtro.' : 'Adicione uma gravação e transforme o discovery em documentação.'}</p>${query || filter !== 'all' ? '<button class="button secondary" id="resetFilters">Limpar filtros</button>' : '<a href="#new" class="button primary">Criar primeira análise →</a>'}</div>`;
            $('resetFilters')?.addEventListener('click', () => { $('searchJobs').value = ''; $('statusFilter').value = 'all'; renderHistory(); });
        }
        $('recentSection').hidden = !jobs.length;
        const recent = jobs.slice(0, 3).map(job => `<a class="recent-job" href="#job=${encodeURIComponent(job.id)}"><div><strong>${escape(job.title)}</strong><small>${date(job.created_at)}${job.delivery_missing ? ' · Arquivos ausentes' : ''}</small></div>${badge(job.status)}</a>`).join('');
        if ($('recentJobs').dataset.signature !== recent) {
            $('recentJobs').dataset.signature = recent;
            $('recentJobs').innerHTML = recent;
        }
    }
    let jobsRequest = 0;
    async function loadJobs(force = false) {
        if (state.jobsLoading && !force)
            return;
        const sequence = ++jobsRequest;
        state.jobsLoading = true;
        $('refresh').disabled = true;
        try {
            const jobs = await api('/api/jobs');
            if (sequence !== jobsRequest)
                return;
            if (!Array.isArray(jobs))
                throw new Error('O histórico retornou um formato inesperado.');
            state.jobs = jobs;
            renderHistory();
            $('connectionNotice').hidden = true;
        }
        catch (error) {
            if (sequence !== jobsRequest)
                return;
            $('connectionNotice').hidden = false;
            if (!state.jobs.length)
                $('jobs').innerHTML = `<div class="empty-state"><h3>Não foi possível carregar as análises</h3><p>${escape(error.message)}</p><button id="retryHistory" class="button secondary">Tentar novamente</button></div>`;
            $('retryHistory')?.addEventListener('click', () => loadJobs(true));
        }
        finally {
            if (sequence === jobsRequest) {
                state.jobsLoading = false;
                $('refresh').disabled = false;
            }
        }
    }
    $('jobs').addEventListener('click', event => {
        const button = event.target.closest('[data-job-action]');
        if (button)
            jobAction(button.dataset.job, button.dataset.jobAction);
    });
    $('searchJobs').addEventListener('input', renderHistory);
    $('statusFilter').addEventListener('change', renderHistory);
    $('refresh').onclick = loadJobs;
    function selectTab(name, focus = false) {
        if (!['Previews', 'Documents', 'Request', 'Activity'].includes(name))
            return;
        document.querySelectorAll('[data-tab]').forEach(button => {
            const selected = button.dataset.tab === name;
            button.setAttribute('aria-selected', String(selected));
            button.tabIndex = selected ? 0 : -1;
            $(`panel${button.dataset.tab}`).hidden = !selected;
            if (selected && focus)
                button.focus();
        });
    }
    document.querySelectorAll('[data-tab]').forEach(button => {
        button.onclick = () => selectTab(button.dataset.tab);
        button.addEventListener('keydown', event => {
            const tabs = Array.from(document.querySelectorAll('[data-tab]'));
            let index = tabs.indexOf(button);
            if (event.key === 'ArrowRight')
                index = (index + 1) % tabs.length;
            else if (event.key === 'ArrowLeft')
                index = (index - 1 + tabs.length) % tabs.length;
            else if (event.key === 'Home')
                index = 0;
            else if (event.key === 'End')
                index = tabs.length - 1;
            else
                return;
            event.preventDefault();
            selectTab(tabs[index].dataset.tab, true);
        });
    });
    function renderPreviews(job) {
        const previews = Array.isArray(job.previews) ? job.previews : [], signature = JSON.stringify([job.id, job.status, job.delivery_missing, job.can_retry, previews]);
        $('previewCount').textContent = previews.filter(item => safeUrl(item.preview_url)).length;
        if ($('previewStack').dataset.signature === signature)
            return;
        $('previewStack').dataset.signature = signature;
        if (job.delivery_missing) {
            $('previewStack').innerHTML = `<div class="empty-state"><span class="empty-icon">${icon('folder')}</span><h3>Os arquivos desta entrega não estão aqui</h3><p>${escape(job.delivery_missing_reason || 'O histórico foi preservado, mas os vídeos e documentos não foram encontrados. Restaure a pasta original do trabalho ou reutilize o pedido e reenvie as gravações.')}</p></div>`;
            return;
        }
        if (!previews.length) {
            $('previewStack').innerHTML = `<div class="empty-state"><span class="empty-icon">${icon('video')}</span><h3>${job.status === 'COMPLETED' ? 'Nenhum preview disponível' : active(job.status) ? 'Seus vídeos vão aparecer aqui' : 'A análise não foi concluída'}</h3><p>${job.status === 'COMPLETED' ? 'Nenhum trecho contextual utilizável foi selecionado. Consulte os avisos e as limitações da documentação.' : active(job.status) ? 'Ao concluir, cada gravação terá seus próprios cortes e opções de download.' : job.can_retry === false ? escape(job.retry_unavailable_reason || 'As gravações não estão disponíveis neste ambiente. Reutilize o pedido e envie os arquivos novamente.') : 'Retome o trabalho para continuar com os mesmos arquivos, ou crie um novo pedido.'}</p></div>`;
            return;
        }
        $('previewStack').innerHTML = previews.map((item, index) => { const url = safeUrl(item.preview_url), download = safeUrl(item.download_url) || url, ranges = Array.isArray(item.ranges) ? item.ranges.filter(range => Number.isFinite(Number(range.start)) && Number.isFinite(Number(range.end)) && Number(range.end) > Number(range.start)) : []; let offset = 0; const cuts = ranges.map((range, cut) => { const target = offset; offset += Number(range.end) - Number(range.start); return `<button type="button" class="cut-row" data-preview-index="${index}" data-seek="${target}"><span>Trecho ${String(cut + 1).padStart(2, '0')}</span><span>${timecode(range.start)} — ${timecode(range.end)}</span><span>Assistir a partir de ${timecode(target)} →</span></button>`; }).join(''); return `<article class="preview-card"><header><span class="preview-number">${String(index + 1).padStart(2, '0')}</span><div class="preview-heading"><h3>${escape(item.source_name || `Gravação ${index + 1}`)}</h3><p>${url ? `${duration(item.duration)} de conteúdo selecionado${item.source_duration ? ` · original ${duration(item.source_duration)}` : ''}` : 'Sem trechos selecionados neste arquivo'}</p></div></header>${url ? `<video id="previewVideo${index}" controls playsinline preload="metadata" aria-label="Preview de ${escape(item.source_name || `gravação ${index + 1}`)}" src="${escape(url)}"></video><footer class="preview-footer"><a class="button secondary" href="${escape(download)}" download>${icon('download')}Baixar este vídeo</a><a class="text-button" href="${escape(url)}" target="_blank" rel="noopener noreferrer">Abrir em nova aba ↗</a></footer>${cuts ? `<details class="cut-list"><summary>${ranges.length} trecho(s) mantido(s) <span>Ver roteiro de cortes</span></summary><p class="caption">Intervalos da gravação original. Clique para navegar no preview.</p>${cuts}</details>` : ''}` : '<div class="preview-empty"><p>A análise não encontrou conteúdo selecionado para o contexto deste pedido nesta gravação.</p></div>'}</article>`; }).join('');
        $('previewStack').querySelectorAll('[data-seek]').forEach(button => {
            button.onclick = () => {
                const video = $(`previewVideo${button.dataset.previewIndex}`);
                if (!video)
                    return;
                const seek = () => { video.currentTime = Math.max(0, Math.min(Number(button.dataset.seek), Number.isFinite(video.duration) ? Math.max(0, video.duration - 0.05) : Number(button.dataset.seek))); video.play().catch(() => toast('O trecho está selecionado. Pressione reproduzir no vídeo.')); };
                if (video.readyState >= 1)
                    seek();
                else
                    video.addEventListener('loadedmetadata', seek, { once: true });
            };
        });
        $('previewStack').querySelectorAll('video').forEach(video => video.addEventListener('error', () => toast('Não foi possível reproduzir este preview. Tente abrir em outra aba ou baixar o arquivo.', true)));
    }
    function renderDocuments(job) {
        const documents = Array.isArray(job.documents) ? job.documents : [], cards = [];
        const add = (title, description, format, url, download = true) => {
            const href = safeUrl(url);
            if (href)
                cards.push(`<a class="document-card" href="${escape(href)}"${download ? ' download' : ' target="_blank" rel="noopener noreferrer"'}><span class="document-icon">${icon(format === 'Vídeo' ? 'video' : 'document')}</span><div class="document-info"><span>${escape(format)}</span><h3>${escape(title)}</h3><p>${escape(description)}</p></div><span aria-hidden="true">${icon(download ? 'download' : 'plus')}</span></a>`);
        };
        if (job.status === 'COMPLETED') {
            add('Relatório navegável', 'Fluxo, regras e evidências reunidos para revisão.', 'HTML', job.report_url, false);
            documents.filter(item => item.available).forEach(item => add(item.label, ({ Word: 'Documento editável para a equipe.', PDF: 'Versão pronta para consulta e compartilhamento.', Markdown: 'Conteúdo em texto estruturado.', CSV: 'Evidências para rastreabilidade.', JSON: 'Dados estruturados da análise.' }[item.format] || 'Arquivo gerado pela análise.'), item.format, item.url));
            add('Gravação analisada', job.recording_size ? bytes(job.recording_size) : 'Referência original do material analisado.', 'Vídeo', job.recording_url);
        }
        const signature = JSON.stringify([job.id, job.status, job.delivery_missing, cards]);
        if ($('documentStack').dataset.signature === signature)
            return;
        $('documentStack').dataset.signature = signature;
        $('documentStack').innerHTML = cards.join('') || `<div class="empty-state"><span class="empty-icon">${icon('document')}</span><h3>${job.status === 'COMPLETED' ? 'Documentação indisponível neste ambiente' : 'A documentação aparece ao concluir'}</h3><p>${job.delivery_missing ? escape(job.delivery_missing_reason) : job.status === 'COMPLETED' ? 'Os arquivos deste trabalho não estão disponíveis neste ambiente. Confira os avisos da análise.' : 'Você receberá o processo, regras, exceções e requisitos de RPA, acompanhados das evidências.'}</p></div>`;
    }
    function renderTiming(job) {
        const timing = job.timing || {}, running = ['RUNNING', 'CANCEL_REQUESTED'].includes(job.status), started = new Date(timing.started_at).getTime();
        let elapsed = Number(timing.elapsed_seconds) || 0;
        if (running && Number.isFinite(started))
            elapsed = Math.max(0, (Date.now() - started) / 1000);
        const terminal = !active(job.status), hasStart = !!timing.started_at && Number.isFinite(started);
        $('elapsedTime').textContent = terminal && !hasStart && elapsed <= 0 ? '—' : duration(elapsed);
        $('timingStart').textContent = hasStart ? `Iniciado em ${date(timing.started_at)}` : terminal ? 'Duração não registrada' : 'Ainda não iniciado';
        const total = Number(timing.estimated_total_seconds), known = timing.estimated_total_seconds !== null && timing.estimated_total_seconds !== undefined && Number.isFinite(total), remaining = known ? Math.max(0, total - elapsed) : null;
        $('remainingTime').textContent = job.status === 'COMPLETED' ? 'Concluído' : job.status === 'CANCELLED' ? 'Cancelado' : job.status === 'FAILED' ? 'Interrompido' : job.status === 'CANCEL_REQUESTED' ? 'Cancelando' : job.status === 'QUEUED' ? 'Após o início' : remaining === null ? 'Calculando…' : remaining < 1 ? 'Atualizando…' : `~ ${duration(remaining)}`;
        $('estimateBasis').textContent = active(job.status) && job.status !== 'QUEUED' ? (timing.basis || 'Aguardando dados suficientes') : 'A estimativa não é um prazo garantido.';
        $('queuePosition').textContent = job.status === 'QUEUED' ? `${timing.queue_position || '—'}º na fila` : job.status === 'COMPLETED' ? (job.delivery_missing ? 'Histórico preservado' : 'Entrega pronta') : job.status === 'FAILED' ? (job.can_retry === false ? 'Reenviar gravações' : 'Revisar e retomar') : job.status === 'CANCELLED' ? (job.source_available === false ? 'Arquivos ausentes' : 'Arquivos preservados') : job.operation === 'rebuild' ? 'Revisão' : 'Em processamento';
        $('totalTime').textContent = known ? `Total estimado: ${duration(total)}` : 'O tempo depende da gravação e das etapas.';
    }
    function syncJobActions(job) {
        $('cancelJob').hidden = !['QUEUED', 'RUNNING', 'CANCEL_REQUESTED'].includes(job.status);
        $('cancelJob').disabled = state.jobAction || job.status === 'CANCEL_REQUESTED';
        $('cancelJob').textContent = job.status === 'CANCEL_REQUESTED' ? 'Cancelando…' : 'Cancelar análise';
        $('retryJob').hidden = !['FAILED', 'CANCELLED'].includes(job.status);
        $('retryJob').disabled = state.jobAction || job.can_retry === false;
        $('retryJob').title = job.can_retry === false ? job.retry_unavailable_reason || 'Os arquivos deste trabalho não estão disponíveis.' : '';
        $('rebuildDocs').hidden = job.status !== 'COMPLETED' || job.can_rebuild === false;
        $('rebuildDocs').disabled = state.jobAction;
        $('reuseRequest').disabled = state.submitting || state.jobAction;
        const packageUrl = safeUrl(job.package_url);
        $('package').hidden = !packageUrl;
        if (packageUrl)
            $('package').href = packageUrl;
        else
            $('package').removeAttribute('href');
        $('sendDrive').hidden = !packageUrl || !state.driveConnected;
        $('sendDrive').disabled = state.jobAction;
    }
    function renderJob(job) {
        state.job = job;
        const result = resultOf(job), progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
        $('detailTitle').textContent = job.title;
        $('detailDate').textContent = `Criado em ${date(job.created_at)}${job.operation === 'rebuild' ? ' · Revisão dos documentos e cortes' : ''}`;
        $('detailBadge').textContent = labels[job.status] || job.status;
        $('detailBadge').className = `badge ${Object.hasOwn(labels, job.status) ? job.status.toLowerCase() : 'queued'}`;
        $('stage').textContent = job.delivery_missing ? 'Arquivos da entrega não encontrados neste ambiente' : job.stage || labels[job.status];
        $('stageProgress').textContent = `${progress}%`;
        $('bar').style.width = `${progress}%`;
        $('jobProgress').setAttribute('aria-valuenow', String(progress));
        $('jobProgress').dataset.status = job.status.toLowerCase();
        const phase = job.status === 'COMPLETED' ? 4 : progress >= 92 ? 3 : progress >= 60 ? 2 : progress >= 35 ? 1 : 0;
        Array.from($('pipelineSteps').children).forEach((element, index) => { element.classList.toggle('complete', index < phase); element.classList.toggle('current', index === phase); });
        message('detailError', job.status === 'FAILED' ? `${job.error || 'O processamento não foi concluído.'} ${job.can_retry === false ? 'Para criar uma nova análise, reutilize o pedido e envie as gravações novamente.' : 'Você pode retomar com os mesmos arquivos. Se a falha persistir, confira o ambiente em Integrações.'}` : '');
        const warnings = Array.isArray(result.warnings) ? result.warnings.filter(item => typeof item === 'string') : [];
        const availabilityWarning = job.delivery_missing ? job.delivery_missing_reason : ['FAILED', 'CANCELLED'].includes(job.status) && job.can_retry === false ? job.retry_unavailable_reason : job.status === 'COMPLETED' && job.can_rebuild === false ? job.rebuild_unavailable_reason : '';
        message('jobWarning', availabilityWarning || (job.status === 'COMPLETED' ? warnings.join(' ') : job.status === 'CANCEL_REQUESTED' ? 'O cancelamento foi solicitado. A etapa em execução será interrompida no próximo ponto seguro.' : job.status === 'CANCELLED' ? 'Este trabalho foi cancelado. As gravações foram preservadas e podem ser usadas em uma nova tentativa.' : ''));
        $('metrics').hidden = job.status !== 'COMPLETED';
        if (job.status === 'COMPLETED') {
            const previews = Array.isArray(job.previews) ? job.previews : [], seconds = previews.reduce((sum, item) => sum + (Number(item.duration) || 0), 0);
            $('metrics').innerHTML = [[result.process_step_count ?? result.step_count ?? '—', 'etapas documentadas'], [result.evidence_count ?? '—', 'evidências analisadas'], [previews.filter(item => safeUrl(item.preview_url)).length, 'previews disponíveis'], [job.delivery_missing ? '—' : duration(seconds), 'conteúdo selecionado']].map(([value, label]) => `<div class="metric"><strong>${escape(value)}</strong><span>${label}</span></div>`).join('');
        }
        $('requestContext').textContent = job.process_context?.trim() || 'Nenhum guia adicional foi informado para este trabalho.';
        $('requestMeta').innerHTML = [['Público', job.audience || 'Equipe de RPA'], ['Detalhamento', detailLabels[job.detail_level] || job.detail_level], ['Orçamento de referência', `US$ ${Number(job.api_budget_usd || 0).toFixed(2)} · não é um teto automático`], ['Gravações', result.source_count ?? 'A confirmar na preparação'], ['Autorização', job.api_approved ? 'Processamento com IA autorizado' : 'Não informada'], ['Identificador', job.id]].map(([label, value]) => `<div><dt>${label}</dt><dd>${escape(value)}</dd></div>`).join('');
        const events = Array.isArray(job.events) ? job.events : [];
        $('events').innerHTML = events.slice().reverse().map(event => `<li class="event-item" data-level="${['info', 'warning', 'error', 'success'].includes(event.level) ? event.level : 'info'}"><time>${date(event.created_at)}</time><p>${escape(event.message)}</p></li>`).join('') || '<li class="event-item"><p>Aguardando os primeiros eventos.</p></li>';
        renderTiming(job);
        syncJobActions(job);
        renderPreviews(job);
        renderDocuments(job);
    }
    async function loadDetail(id, force = false) {
        if (state.detailLoading && !force)
            return;
        const sequence = ++state.detailRequest;
        state.detailLoading = true;
        try {
            const job = await api(`/api/jobs/${encodeURIComponent(id)}`);
            if (sequence !== state.detailRequest || state.jobId !== id || state.view !== 'detail')
                return;
            renderJob(job);
            $('connectionNotice').hidden = true;
        }
        catch (error) {
            if (sequence !== state.detailRequest || state.jobId !== id)
                return;
            message('detailError', error.message);
            if (error.status === 404) {
                $('detailTitle').textContent = 'Análise não encontrada';
                $('stage').textContent = 'Este trabalho não está disponível.';
            }
            else
                $('connectionNotice').hidden = !!error.status;
        }
        finally {
            if (sequence === state.detailRequest)
                state.detailLoading = false;
        }
    }
    const actionCopy = { cancel: ['Cancelar esta análise?', 'O trabalho será interrompido no próximo ponto seguro. As gravações serão preservadas para você retomar depois.', 'Cancelar análise'], retry: ['Retomar esta análise?', 'Os mesmos arquivos e o pedido original serão usados. A nova tentativa pode consumir a API já autorizada.', 'Retomar análise'], 'rebuild-documents': ['Revisar documentos e cortes?', 'A transcrição existente será reaproveitada. A revisão entra na fila e pode consumir a API; você poderá acompanhar e cancelar.', 'Iniciar revisão'] };
    async function jobAction(id, action) {
        if (state.jobAction || !actionCopy[action])
            return;
        state.jobAction = true;
        if (state.job)
            syncJobActions(state.job);
        renderHistory();
        try {
            const [title, text, label] = actionCopy[action];
            if (!await ask(title, text, label, action === 'cancel'))
                return;
            const job = await api(`/api/jobs/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
            state.jobs = state.jobs.map(item => item.id === id ? job : item);
            if (state.jobId === id)
                renderJob(job);
            else
                navigate(`job=${encodeURIComponent(id)}`);
            toast(action === 'cancel' ? 'Cancelamento registrado.' : action === 'retry' ? 'Análise retomada e colocada na fila.' : 'Revisão colocada na fila. Acompanhe o andamento.');
            await loadJobs(true);
        }
        catch (error) {
            toast(error.message, true);
            if (state.jobId === id)
                message('detailError', error.message);
        }
        finally {
            state.jobAction = false;
            if (state.job)
                syncJobActions(state.job);
            renderHistory();
        }
    }
    $('cancelJob').onclick = () => state.job && jobAction(state.job.id, 'cancel');
    $('retryJob').onclick = () => state.job && jobAction(state.job.id, 'retry');
    $('rebuildDocs').onclick = () => state.job && jobAction(state.job.id, 'rebuild-documents');
    $('clearQueue').onclick = async () => {
        if (state.jobAction)
            return;
        state.jobAction = true;
        $('clearQueue').disabled = true;
        try {
            if (!await ask('Limpar falhas e cancelados?', 'Os trabalhos com falha ou cancelados, seus uploads e arquivos intermediários serão excluídos deste ambiente. Essa remoção não pode ser desfeita. As análises concluídas e em andamento serão mantidas.', 'Excluir esses trabalhos', true))
                return;
            const result = await api('/api/jobs/cleanup', { method: 'POST' });
            const removed = state.jobs.filter(job => ['FAILED', 'CANCELLED'].includes(job.status)).map(job => job.id);
            state.jobs = state.jobs.filter(job => !removed.includes(job.id));
            if (removed.includes(state.jobId)) {
                state.job = null;
                navigate('history');
            }
            renderHistory();
            await loadJobs(true);
            toast(result.removed_jobs ? `${result.removed_jobs} trabalho(s) e seus arquivos foram removidos. A remoção não pode ser desfeita.` : 'Não havia trabalhos para remover.');
        }
        catch (error) {
            toast(error.message, true);
        }
        finally {
            state.jobAction = false;
            renderHistory();
        }
    };
    $('reuseRequest').onclick = async () => {
        const job = state.job;
        if (!job || state.submitting)
            return;
        const draft = fields(), hasDraft = draft.title.trim() || draft.process_context.trim() || sources().length;
        if (hasDraft && !await ask('Reutilizar este pedido?', 'Os campos e a seleção atual serão substituídos pelo pedido desta análise. Você deverá adicionar as gravações e autorizar o novo processamento.', 'Reutilizar pedido'))
            return;
        applyFields(job);
        state.files = [];
        state.driveFiles = [];
        state.drivePicked.clear();
        $('approved').checked = false;
        renderFiles();
        saveDraft();
        message('error');
        message('fileNotice');
        setStep(1, false);
        navigate('new');
        toast('Pedido copiado. Adicione as gravações para criar a nova análise.');
    };
    $('sendDrive').onclick = async () => {
        const job = state.job;
        if (!job || state.jobAction)
            return;
        state.jobAction = true;
        syncJobActions(job);
        try {
            if (!await ask('Enviar a entrega ao Google Drive?', $('driveFolder').value.trim() ? 'O pacote completo será enviado para a pasta configurada em Integrações.' : 'O pacote completo será enviado à pasta padrão da conta Google conectada.', 'Enviar pacote'))
                return;
            message('driveMessage', 'Enviando o pacote completo…');
            const result = await api(`/api/jobs/${encodeURIComponent(job.id)}/drive`, { method: 'POST', body: JSON.stringify({ folder: $('driveFolder').value.trim() }) });
            if (state.jobId === job.id) {
                message('driveMessage', 'Entrega enviada ao Google Drive.');
                const link = safeUrl(result.webViewLink, true);
                if (link) {
                    const anchor = document.createElement('a');
                    anchor.href = link;
                    anchor.target = '_blank';
                    anchor.rel = 'noopener noreferrer';
                    anchor.textContent = ' Abrir entrega ↗';
                    $('driveMessage').appendChild(anchor);
                }
            }
            toast('Pacote enviado ao Google Drive.');
        }
        catch (error) {
            message('driveMessage', error.message);
            toast(error.message, true);
        }
        finally {
            state.jobAction = false;
            if (state.job)
                syncJobActions(state.job);
        }
    };
    function navigate(hash) {
        if (location.hash === `#${hash}`)
            route();
        else
            location.hash = hash;
    }
    function resetDetail() { state.job = null; $('detailTitle').textContent = 'Carregando análise…'; $('detailDate').textContent = ''; $('detailBadge').textContent = ''; $('stage').textContent = 'Buscando informações…'; $('stageProgress').textContent = '0%'; $('bar').style.width = '0%'; $('jobProgress').setAttribute('aria-valuenow', '0'); ['previewStack', 'documentStack', 'events', 'requestMeta'].forEach(id => { $(id).innerHTML = ''; delete $(id).dataset.signature; }); $('requestContext').textContent = ''; $('metrics').hidden = true; ['cancelJob', 'retryJob', 'rebuildDocs', 'sendDrive', 'package'].forEach(id => { $(id).hidden = true; }); $('reuseRequest').disabled = true; message('detailError'); message('jobWarning'); message('driveMessage'); ['elapsedTime', 'remainingTime', 'queuePosition', 'totalTime'].forEach(id => { $(id).textContent = '—'; }); selectTab('Previews'); }
    function route() {
        const hash = location.hash.slice(1), match = /^job=([a-zA-Z0-9_-]+)$/.exec(hash), view = match ? 'detail' : ['new', 'history', 'settings'].includes(hash) ? hash : 'new', id = match?.[1] || null, changed = state.view !== view || state.jobId !== id;
        if (changed) {
            document.querySelectorAll('#previewStack video').forEach(video => video.pause());
            state.detailRequest++;
            state.detailLoading = false;
        }
        state.view = view;
        state.jobId = id;
        ['new', 'history', 'detail', 'settings'].forEach(name => { $(`view${name[0].toUpperCase() + name.slice(1)}`).hidden = name !== view; });
        document.querySelectorAll('[data-nav]').forEach(link => {
            if (link.dataset.nav === (view === 'detail' ? 'history' : view))
                link.setAttribute('aria-current', 'page');
            else
                link.removeAttribute('aria-current');
        });
        $('pageLabel').textContent = ({ new: 'Nova análise', history: 'Minhas análises', detail: 'Detalhes da análise', settings: 'Integrações' })[view];
        if (changed) {
            const heading = $(({ new: 'newHeading', history: 'historyHeading', detail: 'detailTitle', settings: 'settingsHeading' })[view]);
            heading.tabIndex = -1;
            heading.focus({ preventScroll: true });
            window.scrollTo(0, 0);
        }
        if (view === 'detail') {
            if (changed)
                resetDetail();
            loadDetail(id, true);
        }
        else if (view === 'history')
            loadJobs(true);
        else if (view === 'settings') {
            checkHealth();
            loadDrive();
        }
    }
    window.addEventListener('hashchange', route);
    let pollTimer, healthCounter = 0;
    function schedulePoll() {
        clearTimeout(pollTimer);
        if (document.hidden)
            return;
        pollTimer = setTimeout(async () => {
            const work = [loadJobs()];
            if (state.view === 'detail' && state.jobId)
                work.push(loadDetail(state.jobId));
            if (++healthCounter % 6 === 0)
                work.push(checkHealth());
            await Promise.allSettled(work);
            schedulePoll();
        }, 5000);
    }
    document.addEventListener('visibilitychange', () => {
        clearTimeout(pollTimer);
        if (!document.hidden) {
            loadJobs(true);
            if (state.view === 'detail' && state.jobId)
                loadDetail(state.jobId, true);
            schedulePoll();
        }
    });
    setInterval(() => {
        if (!document.hidden && state.view === 'detail' && state.job)
            renderTiming(state.job);
    }, 1000);
    renderFiles();
    setStep(1, false);
    route();
    Promise.allSettled([checkHealth(), loadDrive(), loadJobs()]);
    schedulePoll();
    if (new URL(location.href).searchParams.get('drive') === 'connected') {
        toast('Conta Google conectada. Você já pode escolher as gravações.');
        const url = new URL(location.href);
        url.searchParams.delete('drive');
        history.replaceState(null, '', url);
    }
})();
