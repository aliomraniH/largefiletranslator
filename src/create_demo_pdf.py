"""Create a demo French PDF file for testing the translation pipeline."""

import os
from fpdf import FPDF

from src.config import TEMP_DIR

DEMO_FILENAME = "document_francais_demo.pdf"

FRENCH_CONTENT = [
    {
        "title": "Introduction à l'Intelligence Artificielle",
        "body": (
            "L'intelligence artificielle (IA) est un domaine de l'informatique qui vise "
            "à créer des systèmes capables de réaliser des tâches qui nécessitent "
            "normalement l'intelligence humaine. Ces tâches comprennent l'apprentissage, "
            "le raisonnement, la résolution de problèmes, la perception et la compréhension "
            "du langage naturel.\n\n"
            "Depuis ses débuts dans les années 1950, l'IA a connu des avancées remarquables. "
            "Les premiers systèmes étaient basés sur des règles simples, mais les approches "
            "modernes utilisent des réseaux de neurones profonds et l'apprentissage automatique "
            "pour atteindre des performances impressionnantes dans de nombreux domaines."
        ),
    },
    {
        "title": "Applications de l'IA dans la Vie Quotidienne",
        "body": (
            "L'intelligence artificielle est désormais présente dans de nombreux aspects "
            "de notre vie quotidienne. Les assistants virtuels comme Siri et Alexa utilisent "
            "le traitement du langage naturel pour comprendre et répondre à nos questions. "
            "Les systèmes de recommandation sur Netflix et Spotify analysent nos préférences "
            "pour suggérer du contenu pertinent.\n\n"
            "Dans le domaine de la santé, l'IA aide les médecins à diagnostiquer des maladies "
            "plus rapidement et avec plus de précision. Les algorithmes d'apprentissage "
            "automatique peuvent analyser des images médicales et détecter des anomalies "
            "qui pourraient échapper à l'oeil humain.\n\n"
            "Les véhicules autonomes représentent une autre application majeure de l'IA. "
            "Ces voitures utilisent des capteurs, des caméras et des algorithmes sophistiqués "
            "pour naviguer dans le trafic sans intervention humaine."
        ),
    },
    {
        "title": "Les Défis Éthiques de l'Intelligence Artificielle",
        "body": (
            "Malgré ses nombreux avantages, l'intelligence artificielle soulève également "
            "des questions éthiques importantes. La protection de la vie privée est une "
            "préoccupation majeure, car les systèmes d'IA nécessitent souvent de grandes "
            "quantités de données personnelles pour fonctionner efficacement.\n\n"
            "Le biais algorithmique est un autre défi crucial. Les systèmes d'IA peuvent "
            "perpétuer ou même amplifier les préjugés existants dans les données "
            "d'entraînement. Il est essentiel de développer des méthodes pour détecter "
            "et corriger ces biais afin de garantir l'équité et la justice.\n\n"
            "Enfin, l'impact de l'IA sur l'emploi est une question qui préoccupe de nombreux "
            "experts. Bien que l'IA crée de nouvelles opportunités, elle pourrait également "
            "remplacer certains emplois traditionnels, ce qui nécessite une réflexion "
            "approfondie sur la formation et la reconversion professionnelle."
        ),
    },
]


def create_demo_french_pdf(output_dir: str = None) -> str:
    """Generate a multi-page French PDF for demo purposes.

    Returns the path to the created PDF file.
    """
    if output_dir is None:
        output_dir = TEMP_DIR
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, DEMO_FILENAME)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    for section in FRENCH_CONTENT:
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, section["title"])
        pdf.ln(5)

        # Body
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 7, section["body"])

    pdf.output(output_path)
    print(f"Demo French PDF created: {output_path}")
    return output_path


if __name__ == "__main__":
    path = create_demo_french_pdf()
    print(f"Created at: {path}")
