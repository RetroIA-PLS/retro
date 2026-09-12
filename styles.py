"""CSS centralizado de la aplicación."""

from config import COLORS


def app_css() -> str:
    """Devuelve el CSS de la aplicación."""
    return f"""
    <style>
    .main .block-container {{padding-top: 1.5rem;}}
    .app-title {{font-size: 2rem; font-weight: 750; color: {COLORS['primary_dark']};}}
    .app-subtitle {{color: #52616f; margin-bottom: 1rem;}}
    .section-card {{
        border: 1px solid {COLORS['border']}; border-radius: 14px;
        padding: 1rem; background: white; margin-bottom: 1rem;
    }}
    .metric-card {{
        border: 1px solid {COLORS['border']}; border-radius: 12px;
        padding: .8rem; background: {COLORS['surface']};
    }}
    .small-muted {{color: #607080; font-size: .9rem;}}
    .danger-text {{color: {COLORS['danger']}; font-weight: 600;}}
    .success-text {{color: {COLORS['success']}; font-weight: 600;}}
    textarea {{font-family: ui-monospace, SFMono-Regular, Consolas, monospace;}}
    </style>
    """
