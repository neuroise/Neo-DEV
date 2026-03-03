#!/usr/bin/env node
/**
 * Genera documento Word con le metriche di valutazione NEURØISE
 *
 * Usage: node scripts/create_metrics_doc.js
 */

const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
        Header, Footer, PageNumber, PageBreak } = require('docx');
const fs = require('fs');

// Colori brand
const COLORS = {
    primary: "1E3A5F",      // Blu navy
    secondary: "5A7A9A",    // Blu chiaro
    accent: "2E86AB",       // Blu accent
    sage: "6B7280",         // Grigio
    rebel: "DC2626",        // Rosso
    lover: "DB2777",        // Rosa
    green: "059669",        // Verde (GREEN flag)
    yellow: "D97706",       // Giallo (YELLOW flag)
    red: "DC2626",          // Rosso (RED flag)
    lightBg: "F3F4F6",      // Sfondo chiaro
    headerBg: "E5E7EB"      // Sfondo header tabella
};

// Border style comune
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorders = { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
                    left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } };

// Helper per celle tabella
function createCell(text, options = {}) {
    const { bold, fill, width, align, fontSize } = options;
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
                size: fontSize || 20,
                font: "Arial"
            })]
        })]
    });
}

// Helper per header tabella
function createHeaderCell(text, width) {
    return createCell(text, { bold: true, fill: COLORS.headerBg, width });
}

// Metriche automatiche
const automaticMetrics = [
    { id: "M_AUTO_01", name: "Schema Compliance", source: "Custom",
      desc: "Verifica che l'output JSON sia valido e conforme allo schema definito" },
    { id: "M_AUTO_02", name: "Archetype Consistency", source: "Custom",
      desc: "Verifica che lo stesso archetipo (sage/rebel/lover) sia mantenuto in tutte e 3 le scene" },
    { id: "M_AUTO_03", name: "Role Sequence Valid", source: "Custom",
      desc: "Verifica la sequenza corretta: start → evolve → end" },
    { id: "M_AUTO_04", name: "Story Thread Presence", source: "Custom",
      desc: "Verifica che lo story_thread_hint del profilo sia presente nei prompt generati" },
    { id: "M_AUTO_05", name: "Red Flag Score", source: "Content Moderation",
      desc: "Rileva termini in blacklist (urbano, violenza, contenuti inappropriati)" },
    { id: "M_AUTO_06", name: "Prompt Length Valid", source: "Custom",
      desc: "Verifica che i prompt rispettino i vincoli di lunghezza (50-500 caratteri)" },
    { id: "M_AUTO_07", name: "Archetype Lexical Fit", source: "Lexical Analysis",
      desc: "Misura la presenza di keyword specifiche dell'archetipo nei prompt" },
    { id: "M_AUTO_08", name: "Cross-Scene Coherence", source: "Sentence-BERT",
      desc: "Calcola similarità semantica tra le 3 scene usando embedding" },
    { id: "M_AUTO_09", name: "Prompt Specificity", source: "NLP",
      desc: "Misura la concretezza dei prompt (dettagli visivi, camera, lighting)" },
    { id: "M_AUTO_10", name: "Marine Vocabulary Ratio", source: "Custom",
      desc: "Percentuale di termini del dominio marino/costiero nei prompt" },
    { id: "M_AUTO_11", name: "SCORE Coherence", source: "SCORE Paper (2025)",
      desc: "Coerenza narrativa basata su knowledge graph: entity consistency + emotional arc" },
    { id: "M_AUTO_12", name: "LLM-as-Judge Quality", source: "LLM-as-Judge Survey (2024)",
      desc: "Valutazione automatica con GPT-4/Claude usando rubric strutturata (5 criteri)" },
    { id: "M_AUTO_13", name: "Pacing Progression", source: "Narrative Theory",
      desc: "Verifica la curva di intensità narrativa (establishing → intensifying → resolving)" }
];

// Metriche manuali
const manualMetrics = [
    { id: "M_MAN_01", name: "Archetype Fidelity", evaluator: "Human",
      desc: "Il linguaggio visivo corrisponde all'archetipo? (1-5)" },
    { id: "M_MAN_02", name: "Narrative Coherence", evaluator: "Human",
      desc: "Le 3 scene formano un trittico coerente con progressione chiara? (1-5)" },
    { id: "M_MAN_03", name: "Marine Authenticity", evaluator: "Human",
      desc: "Le scene sono chiaramente marine/costiere senza elementi inappropriati? (1-5)" },
    { id: "M_MAN_04", name: "Production Quality", evaluator: "Human",
      desc: "I prompt sono abbastanza specifici per produzione video high-end? (1-5)" },
    { id: "M_MAN_05", name: "Music-Video Alignment", evaluator: "Human",
      desc: "Il prompt OST complementa il mood visivo e l'archetipo? (1-5)" },
    { id: "M_MAN_06", name: "Emotional Impact", evaluator: "Human",
      desc: "L'esperienza complessiva evoca la risposta emotiva desiderata? (1-5)" },
    { id: "M_MAN_07", name: "Brand Alignment", evaluator: "NoNoise Team",
      desc: "L'output è allineato con gli standard del brand luxury yacht? (1-5)" }
];

// Crea il documento
const doc = new Document({
    styles: {
        default: {
            document: {
                run: { font: "Arial", size: 22 }
            }
        },
        paragraphStyles: [
            {
                id: "Heading1",
                name: "Heading 1",
                basedOn: "Normal",
                next: "Normal",
                quickFormat: true,
                run: { size: 36, bold: true, color: COLORS.primary, font: "Arial" },
                paragraph: { spacing: { before: 400, after: 200 } }
            },
            {
                id: "Heading2",
                name: "Heading 2",
                basedOn: "Normal",
                next: "Normal",
                quickFormat: true,
                run: { size: 28, bold: true, color: COLORS.primary, font: "Arial" },
                paragraph: { spacing: { before: 300, after: 150 } }
            },
            {
                id: "Heading3",
                name: "Heading 3",
                basedOn: "Normal",
                next: "Normal",
                quickFormat: true,
                run: { size: 24, bold: true, color: COLORS.secondary, font: "Arial" },
                paragraph: { spacing: { before: 200, after: 100 } }
            }
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
                    children: [
                        new TextRun({ text: "NEURØISE — Metriche di Valutazione", color: COLORS.secondary, size: 18 })
                    ]
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
            // Titolo
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 100 },
                children: [new TextRun({ text: "🌊", size: 72 })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 100 },
                children: [new TextRun({
                    text: "NEURØISE",
                    size: 56,
                    bold: true,
                    color: COLORS.primary,
                    font: "Arial"
                })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 400 },
                children: [new TextRun({
                    text: "Sistema di Metriche per la Valutazione della Qualità",
                    size: 28,
                    color: COLORS.secondary,
                    font: "Arial"
                })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { after: 600 },
                children: [new TextRun({
                    text: "Versione 1.0 — 26 Gennaio 2026",
                    size: 22,
                    italics: true,
                    color: COLORS.secondary,
                    font: "Arial"
                })]
            }),

            // Executive Summary
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("Executive Summary")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Questo documento descrive il sistema di metriche sviluppato per valutare la qualità degli output generati dal sistema NEURØISE. Le metriche sono organizzate in due categorie: automatiche (calcolate dal sistema) e manuali (valutate da esperti umani).",
                    size: 22
                })]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Il sistema utilizza un approccio ibrido che combina tecniche consolidate dalla letteratura scientifica con metriche custom progettate specificamente per il dominio luxury yacht storytelling.",
                    size: 22
                })]
            }),

            // Sistema di Flag
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("Sistema di Flag")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Ogni output viene classificato con un flag di qualità:",
                    size: 22
                })]
            }),
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [1500, 2000, 5860],
                rows: [
                    new TableRow({ children: [
                        createHeaderCell("Flag", 1500),
                        createHeaderCell("Stato", 2000),
                        createHeaderCell("Significato", 5860)
                    ]}),
                    new TableRow({ children: [
                        createCell("🟢", { align: AlignmentType.CENTER, width: 1500 }),
                        createCell("GREEN", { bold: true, width: 2000 }),
                        createCell("Output valido, nessuna violazione. Procedi con la generazione.", { width: 5860 })
                    ]}),
                    new TableRow({ children: [
                        createCell("🟡", { align: AlignmentType.CENTER, width: 1500 }),
                        createCell("YELLOW", { bold: true, width: 2000 }),
                        createCell("Warning presenti. Revisione manuale consigliata prima di procedere.", { width: 5860 })
                    ]}),
                    new TableRow({ children: [
                        createCell("🔴", { align: AlignmentType.CENTER, width: 1500 }),
                        createCell("RED", { bold: true, width: 2000 }),
                        createCell("Violazioni critiche. Output bloccato, richiesta rigenerazione.", { width: 5860 })
                    ]})
                ]
            }),

            // Page break
            new Paragraph({ children: [new PageBreak()] }),

            // Metriche Automatiche
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("Metriche Automatiche")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Le seguenti metriche vengono calcolate automaticamente dal sistema per ogni output generato. Ciascuna metrica produce un punteggio normalizzato tra 0 e 1.",
                    size: 22
                })]
            }),

            // Tabella metriche automatiche
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [1400, 2200, 2000, 3760],
                rows: [
                    new TableRow({ children: [
                        createHeaderCell("ID", 1400),
                        createHeaderCell("Nome", 2200),
                        createHeaderCell("Fonte", 2000),
                        createHeaderCell("Descrizione", 3760)
                    ]}),
                    ...automaticMetrics.map(m => new TableRow({ children: [
                        createCell(m.id, { width: 1400, fontSize: 18 }),
                        createCell(m.name, { bold: true, width: 2200, fontSize: 18 }),
                        createCell(m.source, { width: 2000, fontSize: 18 }),
                        createCell(m.desc, { width: 3760, fontSize: 18 })
                    ]}))
                ]
            }),

            // Dettaglio metriche chiave
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("Dettaglio Metriche Chiave")]
            }),

            // SCORE
            new Paragraph({
                heading: HeadingLevel.HEADING_3,
                children: [new TextRun("SCORE Coherence (M_AUTO_11)")]
            }),
            new Paragraph({
                spacing: { after: 100 },
                children: [
                    new TextRun({ text: "Fonte: ", bold: true }),
                    new TextRun("\"SCORE: Story Coherence and Reasoning Evaluation\" (2025)")
                ]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Questa metrica utilizza un approccio basato su knowledge graph per valutare la coerenza narrativa del trittico. Analizza due aspetti principali: Entity Consistency (le entità menzionate rimangono coerenti tra le scene) e Emotional Arc (la progressione emotiva segue il pattern atteso start→evolve→end).",
                    size: 22
                })]
            }),

            // LLM-as-Judge
            new Paragraph({
                heading: HeadingLevel.HEADING_3,
                children: [new TextRun("LLM-as-Judge Quality (M_AUTO_12)")]
            }),
            new Paragraph({
                spacing: { after: 100 },
                children: [
                    new TextRun({ text: "Fonte: ", bold: true }),
                    new TextRun("\"LLM-as-Judge Survey\" (2024) + \"JudgeLM\" (2024)")
                ]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Utilizza un LLM (GPT-4 o Claude) come giudice automatico per valutare la qualità complessiva. Il modello riceve l'input (profilo) e l'output (trittico + OST) e assegna punteggi su 5 criteri: Archetype Fidelity, Narrative Coherence, Marine Authenticity, Production Quality, Music-Video Alignment.",
                    size: 22
                })]
            }),

            // Page break
            new Paragraph({ children: [new PageBreak()] }),

            // Metriche Manuali
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("Metriche Manuali")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Le seguenti metriche vengono valutate da esperti umani su una scala da 1 a 5. Per garantire affidabilità statistica, ogni output viene valutato da almeno 3 valutatori indipendenti.",
                    size: 22
                })]
            }),

            // Tabella metriche manuali
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [1400, 2500, 1800, 3660],
                rows: [
                    new TableRow({ children: [
                        createHeaderCell("ID", 1400),
                        createHeaderCell("Nome", 2500),
                        createHeaderCell("Valutatore", 1800),
                        createHeaderCell("Descrizione", 3660)
                    ]}),
                    ...manualMetrics.map(m => new TableRow({ children: [
                        createCell(m.id, { width: 1400, fontSize: 18 }),
                        createCell(m.name, { bold: true, width: 2500, fontSize: 18 }),
                        createCell(m.evaluator, { width: 1800, fontSize: 18 }),
                        createCell(m.desc, { width: 3660, fontSize: 18 })
                    ]}))
                ]
            }),

            // Protocollo di valutazione
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("Protocollo di Valutazione")]
            }),
            new Paragraph({
                spacing: { after: 100 },
                children: [new TextRun({ text: "Per la valutazione manuale:", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "• Ogni output viene mostrato in formato blind (senza sapere quale modello lo ha generato)", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "• 3 valutatori indipendenti assegnano punteggi 1-5 per ogni criterio", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "• L'accordo inter-rater viene misurato con Krippendorff's Alpha", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({ text: "• Il punteggio finale è la media dei 3 valutatori", size: 22 })]
            }),

            // Correlazione
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("Validazione delle Metriche Automatiche")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Per validare che le metriche automatiche siano predittive della qualità percepita, calcoleremo la correlazione (Spearman, Kendall) tra i punteggi automatici e quelli manuali su un subset di 45 output (15 per archetipo).",
                    size: 22
                })]
            }),

            // Page break
            new Paragraph({ children: [new PageBreak()] }),

            // Archetipi
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("Metriche per Archetipo")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "Le metriche di archetype consistency verificano che l'output rispetti le caratteristiche distintive di ciascun archetipo:",
                    size: 22
                })]
            }),

            // Tabella archetipi
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [1800, 3200, 2000, 2360],
                rows: [
                    new TableRow({ children: [
                        createHeaderCell("Archetipo", 1800),
                        createHeaderCell("Stile Visivo", 3200),
                        createHeaderCell("Stile Musicale", 2000),
                        createHeaderCell("BPM", 2360)
                    ]}),
                    new TableRow({ children: [
                        createCell("SAGE", { bold: true, width: 1800 }),
                        createCell("Contemplativo, minimale, movimenti lenti", { width: 3200 }),
                        createCell("Ambient, modern classical", { width: 2000 }),
                        createCell("60-80", { align: AlignmentType.CENTER, width: 2360 })
                    ]}),
                    new TableRow({ children: [
                        createCell("REBEL", { bold: true, width: 1800 }),
                        createCell("Dinamico, bold, alta energia", { width: 3200 }),
                        createCell("Electronic, breakbeat", { width: 2000 }),
                        createCell("120-140", { align: AlignmentType.CENTER, width: 2360 })
                    ]}),
                    new TableRow({ children: [
                        createCell("LOVER", { bold: true, width: 1800 }),
                        createCell("Caldo, intimo, sensuale", { width: 3200 }),
                        createCell("Acoustic, cinematic pop", { width: 2000 }),
                        createCell("70-90", { align: AlignmentType.CENTER, width: 2360 })
                    ]})
                ]
            }),

            // Blacklist
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("Contenuti Bloccati (Red Flags)")]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({
                    text: "I seguenti contenuti generano automaticamente un flag RED e bloccano l'output:",
                    size: 22
                })]
            }),
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [2500, 6860],
                rows: [
                    new TableRow({ children: [
                        createHeaderCell("Categoria", 2500),
                        createHeaderCell("Esempi", 6860)
                    ]}),
                    new TableRow({ children: [
                        createCell("Urbano/Non-marino", { bold: true, width: 2500 }),
                        createCell("city, urban, building, street, road, car, traffic, apartment", { width: 6860 })
                    ]}),
                    new TableRow({ children: [
                        createCell("Violenza/Pericolo", { bold: true, width: 2500 }),
                        createCell("blood, death, violence, weapon, explosion, crash, accident", { width: 6860 })
                    ]}),
                    new TableRow({ children: [
                        createCell("Contenuti Inappropriati", { bold: true, width: 2500 }),
                        createCell("nude, naked, explicit, sexual", { width: 6860 })
                    ]}),
                    new TableRow({ children: [
                        createCell("Natura Non-marina", { bold: true, width: 2500 }),
                        createCell("forest, mountain, desert, jungle, snow, ice", { width: 6860 })
                    ]})
                ]
            }),

            // Conclusioni
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("Prossimi Passi")]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "1. Implementazione completa delle metriche automatiche M_AUTO_01-13", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "2. Baseline testing su 30 profili ufficiali", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "3. Sessione di valutazione manuale con team interno NoNoise", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 50 },
                children: [new TextRun({ text: "4. Calcolo correlazione metriche automatiche vs manuali", size: 22 })]
            }),
            new Paragraph({
                spacing: { after: 200 },
                children: [new TextRun({ text: "5. Raffinamento metriche basato sui risultati", size: 22 })]
            }),

            // Footer
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 400 },
                children: [new TextRun({
                    text: "— Documento preparato per No Noise Srl —",
                    italics: true,
                    color: COLORS.secondary,
                    size: 20
                })]
            })
        ]
    }]
});

// Salva il documento
const outputPath = process.argv[2] || '/sessions/laughing-intelligent-cori/mnt/2025 - NoNoise/neuroise-playground/docs/NEUROISE_Metriche_Valutazione.docx';

// Crea directory se non esiste
const dir = require('path').dirname(outputPath);
if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
}

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log(`✅ Documento creato: ${outputPath}`);
}).catch(err => {
    console.error('Errore:', err);
    process.exit(1);
});
