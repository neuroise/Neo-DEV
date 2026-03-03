#!/usr/bin/env node
/**
 * Genera documento Word DETTAGLIATO con le metriche di valutazione NEURØISE
 *
 * Usage: node scripts/create_metrics_doc_detailed.js
 */

const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
        Header, Footer, PageNumber, PageBreak, NumberFormat } = require('docx');
const fs = require('fs');

// Colori brand
const COLORS = {
    primary: "1E3A5F",
    secondary: "5A7A9A",
    accent: "2E86AB",
    green: "059669",
    yellow: "D97706",
    red: "DC2626",
    lightBg: "F8FAFC",
    headerBg: "E2E8F0",
    codeBg: "F1F5F9"
};

const border = { style: BorderStyle.SINGLE, size: 1, color: "CBD5E1" };
const borders = { top: border, bottom: border, left: border, right: border };

function createCell(text, options = {}) {
    const { bold, fill, width, align, fontSize, italic, color } = options;
    return new TableCell({
        borders,
        width: width ? { size: width, type: WidthType.DXA } : undefined,
        shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({
            alignment: align || AlignmentType.LEFT,
            children: [new TextRun({
                text,
                bold: bold || false,
                italics: italic || false,
                size: fontSize || 20,
                font: "Arial",
                color: color || "000000"
            })]
        })]
    });
}

function createHeaderCell(text, width) {
    return createCell(text, { bold: true, fill: COLORS.headerBg, width });
}

function createCodeBlock(code) {
    return new Paragraph({
        shading: { fill: COLORS.codeBg, type: ShadingType.CLEAR },
        spacing: { before: 100, after: 100 },
        children: [new TextRun({
            text: code,
            font: "Courier New",
            size: 18
        })]
    });
}

function createMetricSection(metric) {
    const elements = [];

    // Titolo metrica
    elements.push(new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun(`${metric.id}: ${metric.name}`)]
    }));

    // Info box
    elements.push(new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        columnWidths: [2000, 7360],
        rows: [
            new TableRow({ children: [
                createCell("Tipo", { bold: true, fill: COLORS.lightBg, width: 2000 }),
                createCell(metric.type, { width: 7360 })
            ]}),
            new TableRow({ children: [
                createCell("Fonte", { bold: true, fill: COLORS.lightBg, width: 2000 }),
                createCell(metric.source, { width: 7360 })
            ]}),
            new TableRow({ children: [
                createCell("Output", { bold: true, fill: COLORS.lightBg, width: 2000 }),
                createCell(metric.output, { width: 7360 })
            ]}),
            new TableRow({ children: [
                createCell("Soglie", { bold: true, fill: COLORS.lightBg, width: 2000 }),
                createCell(metric.thresholds, { width: 7360 })
            ]})
        ]
    }));

    // Descrizione
    elements.push(new Paragraph({
        spacing: { before: 150, after: 100 },
        children: [new TextRun({ text: "Descrizione: ", bold: true }), new TextRun(metric.description)]
    }));

    // Come funziona
    elements.push(new Paragraph({
        spacing: { before: 100, after: 100 },
        children: [new TextRun({ text: "Come funziona: ", bold: true }), new TextRun(metric.howItWorks)]
    }));

    // Formula/Algoritmo se presente
    if (metric.formula) {
        elements.push(new Paragraph({
            spacing: { before: 100, after: 50 },
            children: [new TextRun({ text: "Formula/Algoritmo:", bold: true })]
        }));
        elements.push(createCodeBlock(metric.formula));
    }

    // Esempio
    if (metric.example) {
        elements.push(new Paragraph({
            spacing: { before: 100, after: 100 },
            children: [new TextRun({ text: "Esempio: ", bold: true }), new TextRun(metric.example)]
        }));
    }

    // Limitazioni
    if (metric.limitations) {
        elements.push(new Paragraph({
            spacing: { before: 100, after: 150 },
            children: [new TextRun({ text: "Limitazioni: ", bold: true, color: COLORS.yellow }), new TextRun(metric.limitations)]
        }));
    }

    // Spazio tra metriche
    elements.push(new Paragraph({ spacing: { after: 200 }, children: [] }));

    return elements;
}

// Definizione completa delle metriche
const automaticMetrics = [
    {
        id: "M_AUTO_01",
        name: "Schema Compliance",
        type: "Strutturale",
        source: "Custom (JSON Schema Validation)",
        output: "Binario: 1.0 (valido) o 0.0 (invalido)",
        thresholds: "GREEN: 1.0 | RED: < 1.0",
        description: "Verifica che l'output JSON generato dal Director sia sintatticamente valido e conforme allo schema definito per il trittico video e il prompt OST.",
        howItWorks: "Il sistema valida l'output contro uno JSON Schema che definisce: (1) presenza dei 3 elementi del trittico, (2) campi obbligatori per ogni scena (scene_role, prompt, duration_hint, mood_tags), (3) struttura del prompt OST (prompt, genre, bpm, mood), (4) tipi di dato corretti per ogni campo.",
        formula: "schema_compliance = 1.0 if jsonschema.validate(output, SCHEMA) else 0.0",
        example: "Un output senza il campo 'mood_tags' in una scena → score = 0.0 (RED flag)",
        limitations: "Non valuta la qualità semantica, solo la struttura. Un output può essere valido ma di bassa qualità."
    },
    {
        id: "M_AUTO_02",
        name: "Archetype Consistency",
        type: "Semantica",
        source: "Custom (Lexical Analysis)",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.7 | YELLOW: 0.4-0.7 | RED: < 0.4",
        description: "Verifica che lo stesso archetipo (sage/rebel/lover) sia mantenuto coerentemente in tutte e 3 le scene del trittico e nel prompt OST.",
        howItWorks: "Per ogni archetipo è definito un set di keyword caratteristiche. Il sistema conta quante keyword dell'archetipo corretto appaiono vs keyword di altri archetipi. Il rapporto determina la coerenza.",
        formula: "consistency = correct_keywords / (correct_keywords + other_keywords + epsilon)",
        example: "Profilo SAGE con prompt contenenti 'dynamic', 'energetic', 'crashing' → basso score (keyword REBEL)",
        limitations: "Basato solo su keyword, può mancare sfumature semantiche più sottili."
    },
    {
        id: "M_AUTO_03",
        name: "Role Sequence Valid",
        type: "Strutturale",
        source: "Custom (Narrative Theory)",
        output: "Binario: 1.0 (corretto) o 0.0 (errato)",
        thresholds: "GREEN: 1.0 | RED: < 1.0",
        description: "Verifica che le 3 scene seguano la sequenza narrativa corretta: start → evolve → end.",
        howItWorks: "Estrae il campo 'scene_role' da ogni scena e verifica che l'ordine sia esattamente ['start', 'evolve', 'end']. Qualsiasi altra sequenza è invalida.",
        formula: "valid = 1.0 if roles == ['start', 'evolve', 'end'] else 0.0",
        example: "Sequenza ['start', 'end', 'evolve'] → score = 0.0 (ordine sbagliato)",
        limitations: "Non valuta se il contenuto delle scene rispetta effettivamente la progressione narrativa."
    },
    {
        id: "M_AUTO_04",
        name: "Story Thread Presence",
        type: "Semantica",
        source: "Custom (Lexical Matching)",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.6 | YELLOW: 0.3-0.6 | RED: < 0.3",
        description: "Verifica che lo story_thread_hint specificato nel profilo utente sia effettivamente presente e sviluppato nei prompt generati.",
        howItWorks: "Cerca il thread (es. 'single_cloud_gap', 'wave_hits_rock') e le sue varianti semantiche nei 3 prompt. Calcola in quante scene appare e con quale prominenza.",
        formula: "presence = (scenes_with_thread / 3) * prominence_factor",
        example: "Thread 'calm_tide_mark' menzionato in 2 scene su 3 → score ≈ 0.67",
        limitations: "Richiede mapping manuale delle varianti semantiche per ogni thread."
    },
    {
        id: "M_AUTO_05",
        name: "Red Flag Score",
        type: "Content Safety",
        source: "Content Moderation Best Practices",
        output: "Continuo: 0.0 - 1.0 (1.0 = nessun problema)",
        thresholds: "GREEN: 1.0 | YELLOW: 0.8-1.0 | RED: < 0.8",
        description: "Rileva la presenza di contenuti inappropriati: elementi urbani, violenza, contenuti espliciti, ambienti non-marini.",
        howItWorks: "Mantiene una blacklist di termini vietati divisi per categoria (urbano, violenza, esplicito, non-marino). Cerca ogni termine nei prompt con word-boundary matching. Ogni match riduce lo score.",
        formula: "score = max(0, 1.0 - (blacklist_matches * 0.2))",
        example: "Prompt con 'city skyline in background' → match 'city' → score = 0.8 (YELLOW) o RED se multipli",
        limitations: "Non rileva contenuti problematici espressi con sinonimi o parafrasi non in lista."
    },
    {
        id: "M_AUTO_06",
        name: "Prompt Length Valid",
        type: "Strutturale",
        source: "Text-to-Video Best Practices",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: 1.0 | YELLOW: 0.7-1.0 | RED: < 0.7",
        description: "Verifica che i prompt rispettino i vincoli di lunghezza ottimali per la generazione text-to-video (50-500 caratteri per scena).",
        howItWorks: "Per ogni prompt video, verifica: (1) lunghezza minima 50 caratteri (sufficiente dettaglio), (2) lunghezza massima 500 caratteri (evita confusione per il modello T2V). Score = media delle 3 scene.",
        formula: "scene_score = 1.0 if 50 ≤ len(prompt) ≤ 500 else 0.5 if 30 ≤ len ≤ 600 else 0.0",
        example: "Prompt di 40 caratteri 'Calm sea at sunset with gentle waves' → troppo generico → score = 0.5",
        limitations: "Non valuta la qualità del contenuto, solo la quantità. Un prompt lungo può essere ripetitivo."
    },
    {
        id: "M_AUTO_07",
        name: "Archetype Lexical Fit",
        type: "Semantica",
        source: "Lexical Analysis + Domain Knowledge",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.5 | YELLOW: 0.3-0.5 | RED: < 0.3",
        description: "Misura la presenza di vocabolario specifico dell'archetipo target nei prompt generati.",
        howItWorks: "Ogni archetipo ha un dizionario di keyword caratteristiche: SAGE (contemplative, minimal, serene, philosophical...), REBEL (dynamic, bold, powerful, energetic...), LOVER (warm, intimate, sensual, gentle...). Il sistema conta le keyword presenti.",
        formula: "fit = archetype_keywords_found / expected_keywords_count",
        example: "SAGE prompt con 'serene horizon, contemplative mood, timeless vastness' → 3 keyword → score alto",
        limitations: "Dizionari richiedono manutenzione. Nuovi termini validi potrebbero non essere riconosciuti."
    },
    {
        id: "M_AUTO_08",
        name: "Cross-Scene Coherence",
        type: "Semantica",
        source: "Sentence-BERT (Reimers & Gurevych, 2019)",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.6 | YELLOW: 0.4-0.6 | RED: < 0.4",
        description: "Calcola la similarità semantica tra le 3 scene del trittico usando embedding neurali per verificare coerenza narrativa.",
        howItWorks: "Usa Sentence-BERT (all-MiniLM-L6-v2) per generare embedding 384-dim per ogni prompt. Calcola cosine similarity tra coppie di scene. Lo score finale è la media delle 3 similarità pairwise.",
        formula: "coherence = mean(cos_sim(s1,s2), cos_sim(s2,s3), cos_sim(s1,s3))",
        example: "Scene tutte su 'calm morning sea' → embedding simili → coherence ≈ 0.85",
        limitations: "Troppa similarità potrebbe indicare ripetitività (scene identiche). Serve bilanciamento."
    },
    {
        id: "M_AUTO_09",
        name: "Prompt Specificity",
        type: "Qualità",
        source: "NLP Concreteness Analysis",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.6 | YELLOW: 0.4-0.6 | RED: < 0.4",
        description: "Misura quanto i prompt siano concreti e specifici (dettagli visivi, camera, lighting) vs vaghi e generici.",
        howItWorks: "Cerca indicatori di specificità: (1) direzioni camera (wide shot, close-up, tracking), (2) lighting (golden hour, soft light, high contrast), (3) soggetti concreti (waves, rocks, horizon), (4) movimenti (slow pan, static, gentle drift). Più indicatori = più specifico.",
        formula: "specificity = (camera_hints + lighting_hints + concrete_subjects) / max_possible",
        example: "'Gentle waves' (generico) vs 'Slow tracking shot of foam patterns at golden hour, soft diffused light' (specifico)",
        limitations: "Non valuta se le specifiche sono effettivamente realizzabili o coerenti tra loro."
    },
    {
        id: "M_AUTO_10",
        name: "Marine Vocabulary Ratio",
        type: "Domain Compliance",
        source: "Custom Domain Lexicon",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.3 | YELLOW: 0.15-0.3 | RED: < 0.15",
        description: "Misura la percentuale di termini del dominio marino/costiero nei prompt rispetto al totale delle parole.",
        howItWorks: "Mantiene un dizionario di 50+ termini marini (sea, ocean, wave, tide, shore, coast, horizon, salt, breeze, nautical, yacht, foam, spray, reef, current...). Conta occorrenze e calcola rapporto su parole totali.",
        formula: "ratio = marine_terms_count / total_word_count",
        example: "Prompt 100 parole con 25 termini marini → ratio = 0.25 (YELLOW, quasi GREEN)",
        limitations: "Non considera contesto. 'The sea was not visible' conta 'sea' anche se nega la sua presenza."
    },
    {
        id: "M_AUTO_11",
        name: "SCORE Narrative Coherence",
        type: "Semantica Avanzata",
        source: "SCORE Paper (2025) - arXiv:2503.23512",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.7 | YELLOW: 0.5-0.7 | RED: < 0.5",
        description: "Valuta la coerenza narrativa usando approccio basato su knowledge graph, tracciando entity consistency e emotional arc progression.",
        howItWorks: "Implementazione semplificata di SCORE: (1) Entity Consistency: estrae entità/noun chunks con spaCy, calcola overlap Jaccard tra scene (entità che persistono = storia coerente). (2) Emotional Arc: usa embedding per verificare che scena 2 sia 'tra' 1 e 3 (progressione narrativa). Score finale = 0.6*entity + 0.4*emotional.",
        formula: "entity_consistency = mean(jaccard(entities_i, entities_j))\nemotional_arc = 1.0 if dist(s1,s2) + dist(s2,s3) ≈ dist(s1,s3)\nscore = 0.6 * entity_consistency + 0.4 * emotional_arc",
        example: "Trittico con 'lone sailboat' in tutte le scene → alta entity consistency → score alto",
        limitations: "Implementazione semplificata rispetto al paper originale. Non usa full knowledge graph."
    },
    {
        id: "M_AUTO_12",
        name: "LLM-as-Judge Quality",
        type: "Valutazione LLM",
        source: "LLM-as-Judge Survey (2024) arXiv:2411.15594 + JudgeLM",
        output: "Continuo: 0.0 - 1.0 (media 5 criteri)",
        thresholds: "GREEN: ≥ 0.7 | YELLOW: 0.5-0.7 | RED: < 0.5",
        description: "Usa GPT-4 o Claude come giudice automatico per valutare qualità complessiva con rubric strutturata su 5 criteri.",
        howItWorks: "Invia al LLM giudice: (1) profilo input, (2) output generato, (3) rubric con 5 criteri (Archetype Fidelity, Narrative Coherence, Marine Authenticity, Production Quality, Music-Video Alignment). Il LLM assegna score 1-5 per ogni criterio + reasoning. I punteggi vengono normalizzati 0-1.",
        formula: "score = mean(archetype, coherence, marine, production, alignment) / 5.0",
        example: "Output eccellente su tutti i criteri → scores [5,5,4,5,4] → mean = 4.6 → normalized = 0.92",
        limitations: "Costo API per ogni valutazione. Possibile bias del LLM. Richiede temperature=0 per riproducibilità."
    },
    {
        id: "M_AUTO_13",
        name: "Pacing Progression",
        type: "Narrativa",
        source: "Narrative Theory (Freytag's Pyramid)",
        output: "Continuo: 0.0 - 1.0",
        thresholds: "GREEN: ≥ 0.6 | YELLOW: 0.4-0.6 | RED: < 0.4",
        description: "Verifica che la curva di intensità narrativa segua il pattern atteso: establishing (start) → intensifying (evolve) → resolving (end).",
        howItWorks: "Analizza indicatori di intensità in ogni scena: (1) verbi d'azione, (2) aggettivi intensi, (3) lunghezza frasi, (4) punteggiatura. Verifica che evolve > start e che end abbia closure (termini di risoluzione).",
        formula: "intensity_start < intensity_evolve (rising)\nintensity_end shows resolution patterns\nprogression = (rising_check + resolution_check) / 2",
        example: "Start: 'calm horizon' | Evolve: 'waves crashing, wind rising' | End: 'peaceful aftermath' → pattern corretto",
        limitations: "Euristiche basate su indicatori lessicali, non comprende realmente la narrativa."
    }
];

const manualMetrics = [
    {
        id: "M_MAN_01",
        name: "Archetype Fidelity",
        type: "Valutazione Esperta",
        source: "Human Evaluation",
        output: "Scala Likert 1-5",
        thresholds: "5: eccellente | 4: buono | 3: sufficiente | 2: insufficiente | 1: inadeguato",
        description: "Il linguaggio visivo e musicale corrisponde alle caratteristiche dell'archetipo assegnato?",
        howItWorks: "Il valutatore riceve: (1) nome dell'archetipo e sua descrizione, (2) trittico video prompts, (3) OST prompt. Valuta quanto l'output riflette le caratteristiche attese (es. SAGE = contemplativo, REBEL = dinamico, LOVER = intimo).",
        example: "SAGE con prompts 'serene horizons, minimal composition, philosophical stillness' → score 5",
        limitations: "Soggettivo. Richiede training dei valutatori sulle caratteristiche degli archetipi."
    },
    {
        id: "M_MAN_02",
        name: "Narrative Coherence",
        type: "Valutazione Esperta",
        source: "Human Evaluation",
        output: "Scala Likert 1-5",
        thresholds: "5: storia fluida | 4: buona progressione | 3: accettabile | 2: discontinua | 1: incoerente",
        description: "Le 3 scene formano un trittico narrativo coerente con chiara progressione start→evolve→end?",
        howItWorks: "Il valutatore legge i 3 prompt in sequenza e valuta: (1) connessione logica tra scene, (2) progressione narrativa percepibile, (3) senso di completezza del trittico, (4) assenza di contraddizioni.",
        example: "Scene che raccontano 'alba sul mare → sole alto → tramonto' → coerenza narrativa alta",
        limitations: "Interpretazione soggettiva della 'coerenza'. Diversi valutatori possono avere standard diversi."
    },
    {
        id: "M_MAN_03",
        name: "Marine Authenticity",
        type: "Valutazione Esperta",
        source: "Human Evaluation",
        output: "Scala Likert 1-5",
        thresholds: "5: puro marino | 4: prevalente marino | 3: accettabile | 2: elementi estranei | 1: non marino",
        description: "Le scene sono chiaramente marine/costiere senza elementi urbani, terrestri o inappropriati?",
        howItWorks: "Il valutatore verifica: (1) assenza di elementi urbani (edifici, strade, auto), (2) presenza dominante di elementi marini (mare, onde, costa, cielo), (3) assenza di elementi terrestri non costieri (foreste, montagne, deserti).",
        example: "Prompt con 'distant lighthouse on rocky coast' → elemento marino autentico → score alto",
        limitations: "Confine tra 'costiero' e 'terrestre' può essere ambiguo (es. vegetazione costiera)."
    },
    {
        id: "M_MAN_04",
        name: "Production Quality",
        type: "Valutazione Esperta",
        source: "Human Evaluation (preferibilmente filmmaker/creative director)",
        output: "Scala Likert 1-5",
        thresholds: "5: production-ready | 4: buono | 3: usabile | 2: vago | 1: inutilizzabile",
        description: "I prompt sono abbastanza specifici e professionali per guidare una produzione video high-end?",
        howItWorks: "Il valutatore (idealmente con esperienza video) valuta: (1) presenza di direzioni camera, (2) specifiche di lighting, (3) dettagli su composizione, (4) indicazioni di movimento, (5) chiarezza complessiva per un operatore video.",
        example: "'Wide establishing shot, golden hour lighting, slow dolly towards horizon, 24fps cinematic' → molto specifico",
        limitations: "Richiede esperienza nel settore video production per valutazione accurata."
    },
    {
        id: "M_MAN_05",
        name: "Music-Video Alignment",
        type: "Valutazione Esperta",
        source: "Human Evaluation",
        output: "Scala Likert 1-5",
        thresholds: "5: perfetto match | 4: buon match | 3: accettabile | 2: disallineato | 1: contraddittorio",
        description: "Il prompt OST complementa il mood visivo del trittico e l'archetipo?",
        howItWorks: "Il valutatore legge insieme prompts video e OST, valutando: (1) coerenza di mood, (2) match di energia/ritmo, (3) appropriatezza del genere musicale per le immagini, (4) coerenza con l'archetipo.",
        example: "Video SAGE contemplativo + OST 'ambient, 65bpm, ethereal pads' → alignment eccellente",
        limitations: "Richiede capacità di 'immaginare' video e musica insieme. Altamente soggettivo."
    },
    {
        id: "M_MAN_06",
        name: "Emotional Impact",
        type: "Valutazione Esperta",
        source: "Human Evaluation",
        output: "Scala Likert 1-5",
        thresholds: "5: molto evocativo | 4: evocativo | 3: neutro | 2: debole | 1: nessun impatto",
        description: "L'esperienza complessiva (video + musica) evoca la risposta emotiva desiderata per l'archetipo?",
        howItWorks: "Il valutatore immagina l'esperienza completa e valuta: (1) evocatività emotiva, (2) appropriatezza per contesto luxury yacht, (3) capacità di creare connessione con l'ospite, (4) memorabilità.",
        example: "Trittico LOVER con immagini intime + musica romantica che evoca senso di connessione → alto impatto",
        limitations: "Metrica più soggettiva. Dipende fortemente dalla sensibilità del valutatore."
    },
    {
        id: "M_MAN_07",
        name: "Brand Alignment",
        type: "Valutazione Business",
        source: "NoNoise Team Evaluation",
        output: "Scala Likert 1-5",
        thresholds: "5: on-brand | 4: allineato | 3: accettabile | 2: off-brand | 1: inappropriato",
        description: "L'output è allineato con gli standard e i valori del brand luxury yacht NoNoise?",
        howItWorks: "Valutazione specifica del team NoNoise basata su: (1) coerenza con brand guidelines, (2) appropriatezza per clientela luxury, (3) allineamento con estetica Sanlorenzo/Bluegame, (4) professionalità complessiva.",
        example: "Output elegante, sofisticato, senza elementi cheap o volgari → perfetto brand alignment",
        limitations: "Può essere valutato solo dal team NoNoise. Richiede conoscenza brand guidelines interne."
    }
];

// Costruisci il documento
const doc = new Document({
    styles: {
        default: {
            document: { run: { font: "Arial", size: 22 } }
        },
        paragraphStyles: [
            { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 40, bold: true, color: COLORS.primary, font: "Arial" },
              paragraph: { spacing: { before: 400, after: 200 } } },
            { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 32, bold: true, color: COLORS.primary, font: "Arial" },
              paragraph: { spacing: { before: 300, after: 150 } } },
            { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 26, bold: true, color: COLORS.accent, font: "Arial" },
              paragraph: { spacing: { before: 250, after: 100 } } }
        ]
    },
    sections: [{
        properties: {
            page: {
                size: { width: 12240, height: 15840 },
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        headers: {
            default: new Header({
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({ text: "NEURØISE — Documentazione Metriche v1.0", color: COLORS.secondary, size: 18 })]
                })]
            })
        },
        footers: {
            default: new Footer({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({ text: "Pagina ", size: 18 }),
                        new TextRun({ children: [PageNumber.CURRENT], size: 18 }),
                        new TextRun({ text: " — No Noise × DII UniPisa — Confidenziale", size: 18, color: COLORS.secondary })
                    ]
                })]
            })
        },
        children: [
            // Cover page
            new Paragraph({ spacing: { after: 600 }, children: [] }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "🌊", size: 96 })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 200, after: 100 },
                children: [new TextRun({ text: "NEURØISE", size: 72, bold: true, color: COLORS.primary, font: "Arial" })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 200 },
                children: [new TextRun({ text: "Intelligent Storytelling Engine", size: 32, color: COLORS.secondary, font: "Arial" })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 400 },
                children: [new TextRun({ text: "Documentazione Completa delle Metriche di Valutazione", size: 28, bold: true, font: "Arial" })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 200 },
                children: [new TextRun({ text: "Versione 1.0", size: 24, font: "Arial" })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "26 Gennaio 2026", size: 22, italics: true, color: COLORS.secondary, font: "Arial" })]
            }),
            new Paragraph({ spacing: { after: 400 }, children: [] }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "No Noise Srl × DII Università di Pisa", size: 22, color: COLORS.secondary, font: "Arial" })]
            }),

            new Paragraph({ children: [new PageBreak()] }),

            // Indice
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Indice")] }),
            new Paragraph({ children: [new TextRun("1. Introduzione")] }),
            new Paragraph({ children: [new TextRun("2. Sistema di Flag (GREEN/YELLOW/RED)")] }),
            new Paragraph({ children: [new TextRun("3. Metriche Automatiche (M_AUTO_01 - M_AUTO_13)")] }),
            new Paragraph({ children: [new TextRun("4. Metriche Manuali (M_MAN_01 - M_MAN_07)")] }),
            new Paragraph({ children: [new TextRun("5. Protocollo di Validazione")] }),
            new Paragraph({ children: [new TextRun("6. Prossimi Passi")] }),

            new Paragraph({ children: [new PageBreak()] }),

            // Introduzione
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("1. Introduzione")] }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun("Questo documento descrive in dettaglio il sistema di metriche sviluppato per valutare la qualità degli output generati da NEURØISE, l'Intelligent Storytelling Engine per esperienze yacht di lusso.")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun("Il sistema produce per ogni profilo utente:")]
            }),
            new Paragraph({ children: [new TextRun("• Video Triptych: 3 prompt video (start → evolve → end)")] }),
            new Paragraph({ children: [new TextRun("• OST Prompt: prompt per colonna sonora originale")] }),
            new Paragraph({
                spacing: { before: 200, after: 200 },
                children: [new TextRun("Le metriche sono divise in due categorie: 13 metriche automatiche (calcolate dal sistema) e 7 metriche manuali (valutate da esperti). L'approccio ibrido garantisce sia scalabilità che qualità.")]
            }),

            // Sistema di Flag
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("2. Sistema di Flag")] }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun("Ogni output viene classificato con un flag che determina se può procedere alla generazione video/audio:")]
            }),
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [1200, 1800, 6360],
                rows: [
                    new TableRow({ children: [
                        createHeaderCell("Flag", 1200),
                        createHeaderCell("Stato", 1800),
                        createHeaderCell("Azione", 6360)
                    ]}),
                    new TableRow({ children: [
                        createCell("🟢", { align: AlignmentType.CENTER, width: 1200, fontSize: 28 }),
                        createCell("GREEN", { bold: true, width: 1800, color: COLORS.green }),
                        createCell("Output valido. Procedi alla generazione video/audio.", { width: 6360 })
                    ]}),
                    new TableRow({ children: [
                        createCell("🟡", { align: AlignmentType.CENTER, width: 1200, fontSize: 28 }),
                        createCell("YELLOW", { bold: true, width: 1800, color: COLORS.yellow }),
                        createCell("Warning presenti. Revisione manuale consigliata. Può procedere con cautela.", { width: 6360 })
                    ]}),
                    new TableRow({ children: [
                        createCell("🔴", { align: AlignmentType.CENTER, width: 1200, fontSize: 28 }),
                        createCell("RED", { bold: true, width: 1800, color: COLORS.red }),
                        createCell("Violazioni critiche. Output BLOCCATO. Rigenerazione richiesta.", { width: 6360 })
                    ]})
                ]
            }),
            new Paragraph({
                spacing: { before: 200 },
                children: [new TextRun({ text: "Logica di aggregazione: ", bold: true }), new TextRun("Se qualsiasi metrica critica è RED → flag finale RED. Se nessuna RED ma almeno una YELLOW → flag finale YELLOW. Altrimenti GREEN.")]
            }),

            new Paragraph({ children: [new PageBreak()] }),

            // Metriche Automatiche
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("3. Metriche Automatiche")] }),
            new Paragraph({
                spacing: { after: 300 },
                children: [new TextRun("Le seguenti 13 metriche vengono calcolate automaticamente dal sistema per ogni output. Ciascuna metrica produce un punteggio normalizzato tra 0.0 e 1.0.")]
            }),

            // Genera sezioni per ogni metrica automatica
            ...automaticMetrics.flatMap(m => createMetricSection(m)),

            new Paragraph({ children: [new PageBreak()] }),

            // Metriche Manuali
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("4. Metriche Manuali")] }),
            new Paragraph({
                spacing: { after: 300 },
                children: [new TextRun("Le seguenti 7 metriche vengono valutate da esperti umani su scala Likert 1-5. Per affidabilità statistica, ogni output viene valutato da almeno 3 valutatori indipendenti.")]
            }),

            // Genera sezioni per ogni metrica manuale
            ...manualMetrics.flatMap(m => createMetricSection(m)),

            new Paragraph({ children: [new PageBreak()] }),

            // Protocollo di Validazione
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("5. Protocollo di Validazione")] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("5.1 Correlazione Automatiche-Manuali")] }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun("Per validare che le metriche automatiche predicano la qualità percepita, calcoleremo correlazioni su un subset di 45 output (15 per archetipo):")]
            }),
            new Paragraph({ children: [new TextRun("• Spearman's ρ: per correlazioni monotoniche")] }),
            new Paragraph({ children: [new TextRun("• Kendall's τ: per concordanza di ranking")] }),
            new Paragraph({
                spacing: { before: 150 },
                children: [new TextRun({ text: "Target: ", bold: true }), new TextRun("ρ ≥ 0.7 per metriche chiave (M_AUTO_11, M_AUTO_12)")]
            }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("5.2 Inter-Rater Reliability")] }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun("Per le metriche manuali, misureremo l'accordo tra valutatori:")]
            }),
            new Paragraph({ children: [new TextRun("• Krippendorff's Alpha: standard per valutazioni ordinali")] }),
            new Paragraph({
                spacing: { before: 150 },
                children: [new TextRun({ text: "Target: ", bold: true }), new TextRun("α ≥ 0.8 (accordo sostanziale)")]
            }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("5.3 Ablation Studies")] }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun("Per verificare l'utilità di ogni metrica, condurremo ablation studies rimuovendo metriche una alla volta e misurando l'impatto sulla capacità predittiva complessiva.")]
            }),

            new Paragraph({ children: [new PageBreak()] }),

            // Prossimi Passi
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("6. Prossimi Passi")] }),
            new Paragraph({
                spacing: { after: 100 },
                children: [new TextRun({ text: "Fase 1 (Gennaio-Febbraio):", bold: true })]
            }),
            new Paragraph({ children: [new TextRun("• Implementazione completa M_AUTO_01-13")] }),
            new Paragraph({ children: [new TextRun("• Baseline testing su 30 profili ufficiali")] }),
            new Paragraph({ children: [new TextRun("• Setup piattaforma valutazione manuale")] }),

            new Paragraph({
                spacing: { before: 150, after: 100 },
                children: [new TextRun({ text: "Fase 2 (Febbraio):", bold: true })]
            }),
            new Paragraph({ children: [new TextRun("• Sessione valutazione manuale (team interno NoNoise)")] }),
            new Paragraph({ children: [new TextRun("• Calcolo correlazioni automatiche-manuali")] }),
            new Paragraph({ children: [new TextRun("• Raffinamento soglie e pesi metriche")] }),

            new Paragraph({
                spacing: { before: 150, after: 100 },
                children: [new TextRun({ text: "Fase 3 (Marzo):", bold: true })]
            }),
            new Paragraph({ children: [new TextRun("• Ablation studies")] }),
            new Paragraph({ children: [new TextRun("• Documentazione finale per paper ACM MM 2026")] }),
            new Paragraph({ children: [new TextRun("• Human evaluation estesa (Prolific se necessario)")] }),

            // Footer finale
            new Paragraph({ spacing: { before: 400 }, children: [] }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                shading: { fill: COLORS.lightBg, type: ShadingType.CLEAR },
                spacing: { before: 200, after: 200 },
                children: [new TextRun({
                    text: "Documento preparato per No Noise Srl — Confidenziale",
                    italics: true,
                    color: COLORS.secondary,
                    size: 20
                })]
            })
        ]
    }]
});

// Salva
const outputPath = '/sessions/laughing-intelligent-cori/mnt/2025 - NoNoise/neuroise-playground/docs/NEUROISE_Metriche_Documentazione_Completa.docx';
const dir = require('path').dirname(outputPath);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log(`✅ Documento creato: ${outputPath}`);
}).catch(err => {
    console.error('Errore:', err);
    process.exit(1);
});
