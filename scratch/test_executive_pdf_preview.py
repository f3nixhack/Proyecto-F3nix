import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import re
import hashlib
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextDocument, QPdfWriter, QPageSize, QPageLayout
from PyQt6.QtCore import QMarginsF

from core.multi_agent_council import DEBATE_MODES, ROLES_CONFIG

PDF_ROLE_STYLES = {
    "estratega": {
        "title": "🔵 Estratega Creativo & Propositivo",
        "bg": "#F0F7FF",
        "border": "#BBDEFB",
        "accent": "#0288D1",
        "badge_bg": "#E1F5FE",
        "title_color": "#01579B"
    },
    "critico": {
        "title": "🔴 Analista Crítico & Auditor de Riesgos",
        "bg": "#FFF5F5",
        "border": "#FFCDD2",
        "accent": "#E53935",
        "badge_bg": "#FFEBEE",
        "title_color": "#B71C1C"
    },
    "cisne_negro": {
        "title": "🦅 Auditor Cisne Negro (Chaos & Stress-Test de Taleb)",
        "bg": "#FAF5FF",
        "border": "#E9D5FF",
        "accent": "#9333EA",
        "badge_bg": "#F3E8FF",
        "title_color": "#6B21A8"
    },
    "sendero_a": {
        "title": "🅰️ Simulador Sendero A (Horizonte 3-6 Meses)",
        "bg": "#F0F9FF",
        "border": "#BAE6FD",
        "accent": "#0284C7",
        "badge_bg": "#E0F2FE",
        "title_color": "#0369A1"
    },
    "sendero_b": {
        "title": "🅱️ Simulador Sendero B (Horizonte 3-6 Meses)",
        "bg": "#FFFBEB",
        "border": "#FDE68A",
        "accent": "#D97706",
        "badge_bg": "#FEF3C7",
        "title_color": "#B45309"
    },
    "fisiologo": {
        "title": "🔵 Fisiólogo & Coach de Alto Rendimiento",
        "bg": "#F0FDFA",
        "border": "#99F6E4",
        "accent": "#0D9488",
        "badge_bg": "#CCFBF1",
        "title_color": "#0F766E"
    },
    "traumatologo": {
        "title": "🔴 Traumatólogo & Especialista en Longevidad",
        "bg": "#FFF1F2",
        "border": "#FECDD3",
        "accent": "#E11D48",
        "badge_bg": "#FFE4E6",
        "title_color": "#BE123C"
    },
    "arquitecto": {
        "title": "🔵 Arquitecto Clean Code & Escalabilidad",
        "bg": "#EFF6FF",
        "border": "#BFDBFE",
        "accent": "#2563EB",
        "badge_bg": "#DBEAFE",
        "title_color": "#1D4ED8"
    },
    "seguridad_qa": {
        "title": "🔴 Hacker de Seguridad & Auditor QA",
        "bg": "#FDF2F8",
        "border": "#FBCFE8",
        "accent": "#DB2777",
        "badge_bg": "#FCE7F3",
        "title_color": "#BE185D"
    },
    "estoico": {
        "title": "🔵 Filósofo Estoico (Marco Aurelio & Séneca)",
        "bg": "#F5F3FF",
        "border": "#DDD6FE",
        "accent": "#7C3AED",
        "badge_bg": "#EDE9FE",
        "title_color": "#5B21B6"
    },
    "pragmatico": {
        "title": "🔴 Pragmático Realista & Evaluador de Costos",
        "bg": "#FFF7ED",
        "border": "#FFEDD5",
        "accent": "#EA580C",
        "badge_bg": "#FFEDD5",
        "title_color": "#C2410C"
    },
    "defensor": {
        "title": "🔵 Abogado Defensor (Defensa de la Tesis)",
        "bg": "#F0F9FF",
        "border": "#BAE6FD",
        "accent": "#0284C7",
        "badge_bg": "#E0F2FE",
        "title_color": "#0369A1"
    },
    "fiscal": {
        "title": "🔴 Fiscal Acusador (Impugnación & Contrainterrogatorio)",
        "bg": "#FEF2F2",
        "border": "#FECACA",
        "accent": "#DC2626",
        "badge_bg": "#FEE2E2",
        "title_color": "#B91C1C"
    },
    "evaluador_a": {
        "title": "🔵 Evaluador Independiente Alpha",
        "bg": "#ECFEFF",
        "border": "#A5F3FC",
        "accent": "#0891B2",
        "badge_bg": "#CFFAFE",
        "title_color": "#0E7490"
    },
    "evaluador_b": {
        "title": "🟣 Evaluador Independiente Beta",
        "bg": "#FAF5FF",
        "border": "#E9D5FF",
        "accent": "#9333EA",
        "badge_bg": "#F3E8FF",
        "title_color": "#7E22CE"
    },
    "socratico": {
        "title": "🔍 Auditor Socrático (Interrogatorio Incisivo)",
        "bg": "#EEF2FF",
        "border": "#C7D2FE",
        "accent": "#4F46E5",
        "badge_bg": "#E0E7FF",
        "title_color": "#3730A3"
    },
    "proponente": {
        "title": "🔵 Proponente Inicial del Plan",
        "bg": "#F0F7FF",
        "border": "#BBDEFB",
        "accent": "#0288D1",
        "badge_bg": "#E1F5FE",
        "title_color": "#01579B"
    },
    "steelman": {
        "title": "🛡️ Auditor Steel-Man (Versión Invulnerable)",
        "bg": "#F7FEE7",
        "border": "#D9F99D",
        "accent": "#65A30D",
        "badge_bg": "#ECFCCB",
        "title_color": "#4D7C0F"
    },
    "extractor": {
        "title": "📄 Extracción y Síntesis Previa de Documento",
        "bg": "#F8FAFC",
        "border": "#CBD5E1",
        "accent": "#475569",
        "badge_bg": "#F1F5F9",
        "title_color": "#334155"
    }
}

def generate_sample_pdf():
    app = QApplication.instance() or QApplication(sys.argv)

    topic = "¿Cómo estructurar una rutina física de calistenia y fuerza cuidando articulaciones y nutrición real?"
    user_name = "Fenix"
    salutation = "Comandante"
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    date_stamp = datetime.now().strftime("%Y%m%d_%H%M")
    session_hash = hashlib.md5(f"{topic}_{date_stamp}".encode('utf-8')).hexdigest()[:6].upper()
    doc_id = f"F3NX-{date_stamp[:8]}-{session_hash}"

    mode_id = "sabios_salud"
    mode_info = DEBATE_MODES.get(mode_id, DEBATE_MODES["clasico"])
    
    rounds_count = 2
    role_1_label = mode_info.get("role_1_label", "🔵 Fisiólogo")
    role_2_label = mode_info.get("role_2_label", "🔴 Traumatólogo")
    role_dir_label = mode_info.get("role_director_label", "🟢 Protocolo F3NIX")
    m1 = "llama3.2:3b"
    m2 = "deepseek-r1:8b"
    m_dir = "llama3.1:8b"

    summary_bullets = [
        "Adopción de rutina 4 días (Torso/Pierna) con enfoque en sobrecarga progresiva por palancas mecánicas.",
        "Blindaje articular obligatorio: 8 min de movilidad escapular y calentamiento de rotadores para evitar tendinitis.",
        "Estrategia nutricional de comida real (1.6g/kg proteína) con hidratación electrolítica y 7.5h de sueño reparador."
    ]

    checklist_items = [
        "Definir el espacio de entrenamiento y barra de dominadas estable.",
        "Conseguir banda elástica de resistencia media para calentamiento y descompresión.",
        "Registrar repeticiones del Día 1 en cuaderno o app de notas.",
        "Ajustar la ingesta proteica diaria a comida real sin batidos artificiales innecesarios."
    ]

    output_pdf = os.path.join(os.path.dirname(__file__), "test_executive_sample.pdf")

    # Render turns
    turns_html = []
    turns_data = [
        {
            "role": "fisiologo",
            "model": m1,
            "round": 1,
            "phase": "Ronda 1: Propuesta Fisiológica",
            "reply": "Para calistenia y fuerza funcional sin gimnasio:\n\n1. <b>Distribución Semanal (4 días):</b>\n• Lunes y Jueves: Empuje y Tracción (Dominadas pronas 4x6, Fondos en paralelas 4x8, Flexiones diamante 3x12).\n• Martes y Viernes: Pierna y Core (Pistol squats asistidas 4x8 por pierna, Elevaciones de piernas colgado 4x12).\n\n2. <b>Sobrecarga Progresiva:</b> Aumentar densidad o cambiar palanca mecánica cada 14 días."
        },
        {
            "role": "traumatologo",
            "model": m2,
            "round": 1,
            "phase": "Ronda 1: Auditoría de Longevidad y Articulaciones",
            "reply": "Auditoría de riesgos articulares y recuperación:\n\n1. <b>Peligro en Codos y Hombros:</b> Los fondos en paralelas profundos con el cuerpo frío provocan pinzamiento subacromial y tendinopatía distal del tríceps.\n2. <b>Corrección Obligatoria:</b> 8 minutos de calentamiento con dislocaciones de hombro con banda elástica y rotadores externos.\n3. <b>Nutrición:</b> Asegurar al menos 1.6g/kg de proteína con alimentos enteros (huevos, carnes, legumbres) y caldo de huesos rico en colágeno y glicina."
        },
        {
            "role": "director",
            "model": m_dir,
            "round": 0,
            "phase": "Veredicto Final: Protocolo F3NIX de Rendimiento Sostenible",
            "reply": "DICTAMEN FINAL Y PROTOCOLO INTEGRAL:\n\n1. <b>Consenso Alcanzado:</b> Se adopta la rutina de calistenia de 4 días del Fisiólogo pero supeditada al protocolo de protección articular del Traumatólogo.\n\n2. <b>Plan de Acción Inmediato:</b>\n• Bloque A: Movilidad de muñecas y hombros (8 min).\n• Bloque B: Trabajo de fuerza limpia (35 min).\n• Bloque C: Enfriamiento y descompresión espinal (5 min).\n\n3. <b>Nutrición & Sueño:</b> Ventana de hidratación con sal marina y magnesio post-entreno; mínimo 7.5 horas de sueño reparador para recuperar el SNC."
        }
    ]

    total_turns = len(turns_data)
    for i, turn in enumerate(turns_data):
        role = turn["role"]
        model = turn["model"]
        reply = turn["reply"].replace("\n", "<br>")
        round_num = turn["round"]
        phase = turn["phase"]
        is_final = (role == "director" and i == total_turns - 1)

        if is_final:
            turns_html.append(f"""
            <div style="margin-top: 18px; margin-bottom: 16px; padding: 16px 18px; background-color: #ECFDF5; border: 2px solid #059669; border-left: 8px solid #047857; border-radius: 8px;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                    <tr>
                        <td style="background-color: #047857; color: #FFFFFF; padding: 7px 14px; border-radius: 4px; font-weight: bold; font-size: 11.5pt;">
                            🏆 DICTAMEN DEFINITIVO &bull; PLAN MAESTRO CONSENSUADO
                        </td>
                        <td style="text-align: right; background-color: #047857; color: #A7F3D0; padding: 7px 14px; border-radius: 4px; font-size: 9pt;">
                            Cerebro Director: <b>{model}</b>
                        </td>
                    </tr>
                </table>
                <div style="font-size: 9.5pt; color: #065F46; font-weight: bold; margin-bottom: 8px;">
                    🟢 Síntesis Ejecutiva bajo la Constitución Mental F3NIX v1.0 &bull; {phase}
                </div>
                <div style="font-size: 10pt; color: #064E3B; line-height: 1.6;">
                    {reply}
                </div>
            </div>
            """)
        else:
            st = PDF_ROLE_STYLES.get(role, {
                "title": role.capitalize(),
                "bg": "#F8FAFC",
                "border": "#E2E8F0",
                "accent": "#475569",
                "badge_bg": "#F1F5F9",
                "title_color": "#1E293B"
            })
            round_txt = f"Ronda {round_num}" if round_num > 0 else "Turno de Análisis"
            phase_txt = f" &bull; {phase}" if phase else ""
            turns_html.append(f"""
            <div style="margin-bottom: 14px; padding: 12px 16px; background-color: {st['bg']}; border: 1.5px solid {st['border']}; border-left: 6px solid {st['accent']}; border-radius: 6px;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 6px;">
                    <tr>
                        <td>
                            <span style="color: {st['title_color']}; font-weight: bold; font-size: 10.5pt;">
                                {st['title']}
                            </span>
                            <span style="color: #64748B; font-size: 8.5pt;">({round_txt}{phase_txt})</span>
                        </td>
                        <td style="text-align: right;">
                            <span style="background-color: {st['badge_bg']}; color: {st['title_color']}; font-size: 8pt; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 1px solid {st['border']};">
                                Cerebro: {model}
                            </span>
                        </td>
                    </tr>
                </table>
                <div style="font-size: 9.5pt; color: #1E293B; line-height: 1.55;">
                    {reply}
                </div>
            </div>
            """)

    # Checklist HTML
    chk_rows = []
    for chk in checklist_items:
        chk_rows.append(f"""
        <tr>
            <td style="width: 28px; vertical-align: top; padding: 4px 0;">
                <div style="width: 14px; height: 14px; border: 2px solid #059669; border-radius: 3px; background-color: #FFFFFF;"></div>
            </td>
            <td style="padding: 3px 0; font-size: 9.5pt; color: #1E293B; line-height: 1.4;">
                {chk}
            </td>
        </tr>
        """)

    checklist_html = f"""
    <div style="margin-top: 14px; margin-bottom: 16px; padding: 12px 16px; background-color: #F8FAFC; border: 1.5px solid #CBD5E1; border-left: 6px solid #0284C7; border-radius: 6px;">
        <div style="font-size: 10pt; font-weight: bold; color: #0369A1; text-transform: uppercase; margin-bottom: 8px;">
            📋 LISTA DE VERIFICACIÓN EJECUTIVA PARA ACCIÓN INMEDIATA
        </div>
        <table style="width: 100%; border-collapse: collapse;">
            {"".join(chk_rows)}
        </table>
    </div>
    """

    # Summary Bullets HTML
    sum_rows = []
    for b in summary_bullets:
        sum_rows.append(f"""
        <div style="margin-bottom: 5px; font-size: 9.5pt; color: #0F172A; line-height: 1.45;">
            <b style="color: #0284C7;">&bull;</b> {b}
        </div>
        """)

    summary_box_html = f"""
    <div style="margin-bottom: 16px; padding: 12px 16px; background-color: #F0F9FF; border: 1.5px solid #BAE6FD; border-left: 6px solid #0284C7; border-radius: 6px;">
        <div style="font-size: 10pt; font-weight: bold; color: #0369A1; text-transform: uppercase; margin-bottom: 6px;">
            📌 RESUMEN EJECUTIVO &bull; DICTAMEN RÁPIDO (TL;DR)
        </div>
        {"".join(sum_rows)}
    </div>
    """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
            color: #1E293B;
            font-size: 9.5pt;
            line-height: 1.5;
        }}
    </style>
    </head>
    <body>
        <!-- Header Banner -->
        <table style="width: 100%; border-collapse: collapse; background-color: #0B132B; border-bottom: 4px solid #00E5FF; border-radius: 6px; margin-bottom: 12px;">
            <tr>
                <td style="padding: 16px 20px; vertical-align: middle;">
                    <div style="font-size: 7.5pt; font-weight: bold; color: #00E5FF; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 3px;">
                        SISTEMA AUTÓNOMO DE INTELIGENCIA ESTRATÉGICA F3NIX
                    </div>
                    <div style="font-size: 16pt; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px; margin-bottom: 3px;">
                        🏛️ INFORME OFICIAL DE MESA REDONDA
                    </div>
                    <div style="font-size: 9pt; color: #94A3B8;">
                        Deliberación Dialéctica Multi-Agente &bull; Evaluación de Riesgos &bull; Plan Maestro
                    </div>
                </td>
                <td style="padding: 16px 20px; text-align: right; vertical-align: middle; width: 170px;">
                    <div style="background-color: #1C2541; border: 1px solid #334155; border-radius: 6px; padding: 6px 10px; text-align: right;">
                        <div style="font-size: 7pt; color: #94A3B8; text-transform: uppercase; font-weight: bold;">CÓDIGO DE SESIÓN</div>
                        <div style="font-size: 10pt; font-weight: bold; color: #00E5FF; font-family: monospace;">{doc_id}</div>
                        <div style="font-size: 6.5pt; color: #64748B;">CLASIFICACIÓN: PRIVADO</div>
                    </div>
                </td>
            </tr>
        </table>

        <!-- Metadata Cards Grid -->
        <table style="width: 100%; border-collapse: separate; border-spacing: 6px; margin-bottom: 10px;">
            <tr>
                <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                    <div style="font-size: 7.5pt; font-weight: bold; color: #64748B; text-transform: uppercase;">👤 COMANDANTE / SOLICITANTE</div>
                    <div style="font-size: 10.5pt; font-weight: bold; color: #0F172A; margin-top: 2px;">{user_name} ({salutation})</div>
                </td>
                <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                    <div style="font-size: 7.5pt; font-weight: bold; color: #64748B; text-transform: uppercase;">📅 REGISTRO & CERTIFICACIÓN</div>
                    <div style="font-size: 10pt; font-weight: bold; color: #0F172A; margin-top: 2px;">{date_str}</div>
                </td>
            </tr>
            <tr>
                <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                    <div style="font-size: 7.5pt; font-weight: bold; color: #0284C7; text-transform: uppercase;">🧠 MODO DE PENSAMIENTO DIALÉCTICO</div>
                    <div style="font-size: 10pt; font-weight: bold; color: #0369A1; margin-top: 2px;">{mode_info['name']}</div>
                    <div style="font-size: 8pt; color: #64748B; margin-top: 2px;">{mode_info['description']}</div>
                </td>
                <td style="width: 50%; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; vertical-align: top;">
                    <div style="font-size: 7.5pt; font-weight: bold; color: #64748B; text-transform: uppercase;">🤖 CONSEJO DE MODELOS ({rounds_count} RONDAS)</div>
                    <div style="font-size: 8.5pt; color: #1E293B; margin-top: 2px;">
                        &bull; {role_1_label}: <b>{m1}</b><br>
                        &bull; {role_2_label}: <b>{m2}</b><br>
                        &bull; {role_dir_label}: <b>{m_dir}</b>
                    </div>
                </td>
            </tr>
        </table>

        <!-- Topic Box -->
        <div style="margin-bottom: 14px; padding: 10px 14px; background-color: #F1F5F9; border: 1px solid #CBD5E1; border-left: 5px solid #00E5FF; border-radius: 6px;">
            <div style="font-size: 7.5pt; font-weight: bold; color: #0891B2; text-transform: uppercase; margin-bottom: 3px;">
                🎯 CONSULTA / DESAFÍO ESTRATÉGICO:
            </div>
            <div style="font-size: 10.5pt; font-weight: bold; color: #0F172A; line-height: 1.4;">
                {topic}
            </div>
        </div>

        <!-- Executive Brief (TL;DR) -->
        {summary_box_html}

        <!-- Deliberation History -->
        <div style="margin-top: 14px; margin-bottom: 10px; font-size: 10.5pt; font-weight: bold; color: #334155; border-bottom: 1.5px solid #E2E8F0; padding-bottom: 4px;">
            📜 DELIBERACIÓN DIALÉCTICA SECUENCIAL
        </div>

        {"".join(turns_html)}

        <!-- Actionable Checklist -->
        {checklist_html}

        <!-- Footer -->
        <div style="margin-top: 20px; border-top: 1px solid #CBD5E1; padding-top: 8px; text-align: center; font-size: 7.5pt; color: #94A3B8;">
            Documento de Inteligencia Estratégica F3NIX &bull; Sistema Autónomo Multi-Agente &bull; Clasificación: Privado / Uso Personal &bull; Autenticidad Verificada
        </div>
    </body>
    </html>
    """

    writer = QPdfWriter(output_pdf)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(12, 12, 12, 12),
        QPageLayout.Unit.Millimeter
    )
    writer.setPageLayout(layout)

    doc = QTextDocument()
    doc.setHtml(full_html)
    doc.print(writer)

    print(f"PDF generado con éxito en: {output_pdf}")
    assert os.path.exists(output_pdf), "El PDF no se creó"
    assert os.path.getsize(output_pdf) > 1000, "El tamaño del PDF es demasiado pequeño"
    print(f"Tamaño del archivo: {os.path.getsize(output_pdf)} bytes")

if __name__ == "__main__":
    generate_sample_pdf()
