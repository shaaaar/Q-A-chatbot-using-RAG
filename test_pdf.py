from src.pdf_loader import load_pdf

pages = load_pdf("data/documents/test.pdf")

for page in pages :
    print("=" * 60)
    print("PAGE:", page["page"])
    print(page["text"][:1000])