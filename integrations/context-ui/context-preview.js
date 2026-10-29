/* Reuses the production form. The host owns uploads, AI, auth and persistence. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const form = window.DiscoveryContextForm;
    let confirmed = false;
    function showReview(event) {
        event?.preventDefault();
        if (!form.validate()) return;
        const context = form.getValue();
        const summary = $('contextSummary');
        summary.replaceChildren();
        const rows = [...form.getSummary()];
        if (context.objetivo) rows.push(['Objetivo', context.objetivo]);
        if (context.sistemas.length) rows.push(['Sistemas e ferramentas', context.sistemas.join(', ')]);
        for (const [label, value] of rows) {
            const row = document.createElement('div');
            const dt = document.createElement('dt'), dd = document.createElement('dd');
            dt.textContent = label; dd.textContent = value;
            row.append(dt, dd); summary.append(row);
        }
        $('contextGuidePreview').value = context.guia;
        $('contextSensitiveNotice').hidden = !context.dadosSensiveis;
        $('contextExportStatus').textContent = '';
        $('contextExportForm').hidden = true;
        $('contextExportReview').hidden = false;
        $('contextReviewTitle').focus();
    }
    form.ready.then(() => {
        const profile = new URLSearchParams(location.search).get('perfil');
        if (profile && Object.hasOwn(window.DiscoveryContextModel.rules.profiles, profile)) {
            form.setValue({...form.getValue(), perfil: profile});
        }
        $('contextLoadStatus').hidden = true;
        $('contextExportForm').hidden = false;
        document.querySelectorAll('[data-icon]').forEach(element => {
            element.textContent = {chevron:'⌄', spark:'✧', info:'ⓘ'}[element.dataset.icon] || '';
            element.setAttribute('aria-hidden', 'true');
        });
        $('contextExportForm').addEventListener('submit', showReview);
        $('contextBack').addEventListener('click', () => {
            $('contextExportReview').hidden = true;
            $('contextExportForm').hidden = false;
            $('perfil').focus();
        });
        $('contextCopy').addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(form.getValue().guia);
                $('contextExportStatus').textContent = 'Guia copiado.';
            } catch (_) {
                $('contextGuidePreview').focus(); $('contextGuidePreview').select();
                $('contextExportStatus').textContent = 'Selecione e copie o guia pelo teclado.';
            }
        });
        $('contextConfirm').addEventListener('click', () => {
            if (confirmed) return;
            confirmed = true;
            document.dispatchEvent(new CustomEvent('discovery:requestready', {
                detail: {contexto: form.getValue(), ...form.getLegacyFields()},
            }));
            $('contextExportStatus').textContent = 'Contexto revisado e pronto para usar na análise.';
        });
        document.addEventListener('discovery:contextchange', () => { confirmed = false; });
    }).catch(() => {
        $('contextLoadStatus').textContent = 'Não foi possível carregar o contexto. Atualize a página para tentar novamente.';
        $('contextLoadStatus').className = 'notice error';
    });
})();
