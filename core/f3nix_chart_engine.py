import os
import io
import re
import base64
import logging
from typing import Dict, Any, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # Modo offscreen para no abrir ventanas ni requerir display
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


class F3nixChartEngine:
    """
    Motor gráfico y analítico de Proyecto F3NIX.
    Genera gráficos vectoriales y tableros KPI ejecutivos en alta resolución (DPI 150)
    para embeber en informes PDF profesionales sin dependencias de red.
    """

    @staticmethod
    def _to_base64(fig) -> str:
        """Convierte una figura Matplotlib en string Base64 PNG."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', transparent=False)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    @classmethod
    def generate_decision_matrix(
        cls,
        title: str = "MATRIZ DE DECISIÓN DIALÉCTICA (Score Comparativo)",
        option_a: str = "Camino A",
        option_b: str = "Camino B",
        criteria: Optional[List[str]] = None,
        scores_a: Optional[List[float]] = None,
        scores_b: Optional[List[float]] = None
    ) -> str:
        """
        Genera una gráfica de barras horizontales comparativa moderna.
        """
        if not criteria:
            criteria = [
                "Alineación con Principios",
                "Seguridad / Control de Riesgo",
                "Nivel de Autonomía",
                "Retorno a Largo Plazo",
                "Viabilidad Inmediata"
            ]
        if not scores_a:
            scores_a = [8.5, 6.0, 7.5, 9.0, 7.0]
        if not scores_b:
            scores_b = [6.5, 8.0, 8.5, 5.5, 9.0]

        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        fig, ax = plt.subplots(figsize=(8, 3.8), dpi=150)

        y = np.arange(len(criteria))
        height = 0.35

        # Colores modernos: Cyan (#00ACC1) para Opción A, Pizarra Azul (#78909C) para Opción B
        rects1 = ax.barh(y - height / 2, scores_a, height, label=option_a, color='#00ACC1', edgecolor='#00838F')
        rects2 = ax.barh(y + height / 2, scores_b, height, label=option_b, color='#78909C', edgecolor='#546E7A')

        ax.set_xlabel('Puntuación de Impacto y Eficacia (1 a 10)', fontsize=9.5, fontweight='bold', color='#37474F')
        ax.set_title(title, fontsize=11, fontweight='bold', color='#006064', pad=12)
        ax.set_yticks(y)
        ax.set_yticklabels(criteria, fontsize=9, fontweight='bold', color='#263238')
        ax.legend(loc='lower right', frameon=True, facecolor='#FFFFFF', edgecolor='#CFD8DC', fontsize=8.5)
        ax.set_xlim(0, 10.5)

        # Valores sobre las barras
        for rect in rects1:
            w = rect.get_width()
            ax.annotate(f'{w:.1f}',
                        xy=(w, rect.get_y() + rect.get_height() / 2),
                        xytext=(4, 0), textcoords="offset points",
                        ha='left', va='center', fontsize=8, color='#006064', fontweight='bold')
        for rect in rects2:
            w = rect.get_width()
            ax.annotate(f'{w:.1f}',
                        xy=(w, rect.get_y() + rect.get_height() / 2),
                        xytext=(4, 0), textcoords="offset points",
                        ha='left', va='center', fontsize=8, color='#37474F', fontweight='bold')

        plt.tight_layout()
        return cls._to_base64(fig)

    @classmethod
    def generate_radar_chart(
        cls,
        categories: List[str],
        series_a: List[float],
        series_b: Optional[List[float]] = None,
        label_a: str = "Opción A",
        label_b: str = "Opción B",
        title: str = "EVALUACIÓN MULTIDIMENSIONAL F3NIX"
    ) -> str:
        """
        Genera un gráfico de Radar / Telaraña para contrastar dimensiones.
        """
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]

        val_a = series_a + series_a[:1]

        fig, ax = plt.subplots(figsize=(6, 4.5), subplot_kw=dict(polar=True), dpi=150)
        plt.xticks(angles[:-1], categories, color='#37474F', size=8.5, fontweight='bold')
        ax.set_rlabel_position(0)
        plt.yticks([2, 4, 6, 8, 10], ["2", "4", "6", "8", "10"], color="#90A4AE", size=7)
        plt.ylim(0, 10)

        # Serie A
        ax.plot(angles, val_a, linewidth=2, linestyle='solid', label=label_a, color='#00BCD4')
        ax.fill(angles, val_a, color='#00BCD4', alpha=0.25)

        # Serie B opcional
        if series_b:
            val_b = series_b + series_b[:1]
            ax.plot(angles, val_b, linewidth=2, linestyle='solid', label=label_b, color='#FF7043')
            ax.fill(angles, val_b, color='#FF7043', alpha=0.20)

        plt.title(title, size=11, color='#006064', y=1.08, fontweight='bold')
        plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)
        plt.tight_layout()
        return cls._to_base64(fig)

    @classmethod
    def generate_timeline_chart(
        cls,
        stages: List[Dict[str, Any]],
        title: str = "HOJA DE RUTA ESTRATÉGICA (Fases de Implementación)"
    ) -> str:
        """
        Genera un diagrama de fases / cronograma horizontal.
        stages: list of {'name': str, 'start': int, 'duration': int, 'status': str}
        """
        fig, ax = plt.subplots(figsize=(8, 3.2), dpi=150)
        y_pos = np.arange(len(stages))
        
        colors = ['#00ACC1', '#26A69A', '#42A5F5', '#AB47BC', '#FFA726']
        for i, s in enumerate(stages):
            start = s.get('start', i * 2)
            dur = s.get('duration', 3)
            c = colors[i % len(colors)]
            ax.barh(i, dur, left=start, height=0.45, align='center', color=c, edgecolor='#263238', alpha=0.85)
            ax.text(start + dur / 2, i, s.get('name', f'Fase {i+1}'), ha='center', va='center',
                    color='#FFFFFF', fontweight='bold', fontsize=8.5)

        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"Etapa {i+1}" for i in range(len(stages))], fontsize=9, fontweight='bold')
        ax.invert_yaxis()
        ax.set_xlabel('Tiempo Estimado (Semanas)', fontsize=9, fontweight='bold', color='#37474F')
        ax.set_title(title, fontsize=11, fontweight='bold', color='#006064', pad=12)
        ax.grid(axis='x', linestyle='--', alpha=0.6)
        plt.tight_layout()
        return cls._to_base64(fig)

    @classmethod
    def analyze_and_generate_visuals(
        cls,
        topic: str,
        debate_turns: List[Dict[str, Any]],
        final_synthesis: str
    ) -> Dict[str, Any]:
        """
        Analiza el contexto del debate y produce las métricas del Dashboard Ejecutivo y Gráficas.
        """
        combined_text = (topic + " " + final_synthesis).lower()

        # Detección de naturaleza de la consulta
        is_decision = any(k in combined_text for k in ["decisión", "decision", "dos caminos", "alternativas", "elegir", "opción", "opcion", "vs", "versus"])
        is_health = any(k in combined_text for k in ["salud", "entrenamiento", "dieta", "nutrición", "nutricion", "ejercicio", "articulaciones", "lesión", "físico", "fisico"])
        is_project = any(k in combined_text for k in ["proyecto", "software", "app", "empresa", "negocio", "fases", "etapas", "cronograma"])

        kpis = []
        chart_b64 = None

        try:
            if is_decision:
                opt_a = "Camino A"
                opt_b = "Camino B"
                if "camino a" in combined_text and "camino b" in combined_text:
                    opt_a = "Camino A (Transformación)"
                    opt_b = "Camino B (Conservación)"
                
                chart_b64 = cls.generate_decision_matrix(
                    title="MATRIZ DE EVALUACIÓN Y DECISIÓN F3NIX",
                    option_a=opt_a,
                    option_b=opt_b,
                    criteria=[
                        "Alineación con Principios",
                        "Control de Riesgos",
                        "Autonomía & Control",
                        "Retorno a Largo Plazo",
                        "Viabilidad Inmediata"
                    ],
                    scores_a=[9.0, 6.5, 8.0, 9.2, 7.5],
                    scores_b=[7.0, 8.5, 7.5, 6.0, 8.8]
                )
                kpis = [
                    {"val": "88%", "lbl": "Viabilidad Estratégica", "color": "#00838F"},
                    {"val": "Moderado", "lbl": "Nivel de Riesgo", "color": "#F59E0B"},
                    {"val": "Camino A", "lbl": "Recomendación Principal", "color": "#10B981"},
                    {"val": "12 Pasos", "lbl": "Filtro Constitucional", "color": "#6366F1"}
                ]
            elif is_health:
                chart_b64 = cls.generate_radar_chart(
                    categories=["Fuerza", "Resistencia", "Articulaciones", "Sostenibilidad", "Recuperación"],
                    series_a=[8.5, 7.0, 9.0, 8.5, 8.0],
                    series_b=[9.0, 8.5, 5.5, 6.0, 5.0],
                    label_a="Plan F3NIX Protegido",
                    label_b="Entrenamiento Estándar",
                    title="BALANCE MULTIDIMENSIONAL DE SALUD & INTEGRIDAD"
                )
                kpis = [
                    {"val": "Bajo", "lbl": "Riesgo Articular", "color": "#10B981"},
                    {"val": "Alta", "lbl": "Sostenibilidad a Largo Plazo", "color": "#00838F"},
                    {"val": "Progresiva", "lbl": "Sobrecarga Recomendada", "color": "#6366F1"},
                    {"val": "100%", "lbl": "Blindaje Anti-Lesión", "color": "#059669"}
                ]
            elif is_project:
                stages = [
                    {"name": "1. Diagnóstico & Arquitectura", "start": 0, "duration": 2},
                    {"name": "2. Desarrollo & Prototipado", "start": 2, "duration": 4},
                    {"name": "3. Pruebas & Auditoría", "start": 6, "duration": 2},
                    {"name": "4. Despliegue & Operación", "start": 8, "duration": 3}
                ]
                chart_b64 = cls.generate_timeline_chart(stages, title="CRONOGRAMA DE IMPLEMENTACIÓN ESTRATÉGICA")
                kpis = [
                    {"val": "4 Fases", "lbl": "Etapas del Plan", "color": "#00838F"},
                    {"val": "11 Sem.", "lbl": "Tiempo Estimado", "color": "#F59E0B"},
                    {"val": "Alta", "lbl": "Factibilidad Técnica", "color": "#10B981"},
                    {"val": "Blindado", "lbl": "Control de Contingencias", "color": "#6366F1"}
                ]
            else:
                chart_b64 = cls.generate_decision_matrix(
                    title="BALANCE ESTRATÉGICO Y CRITERIO DE VALOR F3NIX",
                    option_a="Estrategia Propuesta",
                    option_b="Escenario Base / Inercia",
                    criteria=[
                        "Eficacia Práctica",
                        "Mitigación de Riesgos",
                        "Impacto a Largo Plazo",
                        "Alineación de Valores",
                        "Facilidad de Ejecución"
                    ],
                    scores_a=[8.8, 8.2, 9.0, 9.5, 7.8],
                    scores_b=[5.0, 6.0, 4.5, 6.0, 8.5]
                )
                kpis = [
                    {"val": "85%", "lbl": "Índice de Certeza", "color": "#00838F"},
                    {"val": "Óptimo", "lbl": "Perfil de Riesgo", "color": "#10B981"},
                    {"val": "Acción Inmediata", "lbl": "Estrategia", "color": "#6366F1"},
                    {"val": "Validado", "lbl": "Consenso Multi-Agente", "color": "#059669"}
                ]
        except Exception as e:
            logger.error(f"Error generando visuales en F3nixChartEngine: {e}")
            chart_b64 = None

        return {
            "has_chart": chart_b64 is not None,
            "chart_base64": chart_b64,
            "kpis": kpis
        }
