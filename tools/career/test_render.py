"""render.py: the PDF of a draft. Arya Stark is made up (testdata/)."""

import io
from pathlib import Path

import pytest
from pypdf import PdfReader

import render

TESTDATA = Path(__file__).with_name("testdata")
RESUME = (TESTDATA / "resume.md").read_text()
LETTER = (TESTDATA / "cover-letter.md").read_text()


def text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def lines(md: str) -> list[str]:
    """The draft's lines as they print: no Markdown marks, no blank lines."""
    return [line.lstrip("#- ").replace("**", "") for line in md.splitlines() if line.strip()]


def fonts(pdf: bytes) -> set[str]:
    return {
        f.get_object()["/BaseFont"].split("+")[-1].removesuffix("-Identity-H")
        for page in PdfReader(io.BytesIO(pdf)).pages
        for f in page["/Resources"]["/Font"].values()
    }


def test_aryas_resume_is_one_page_with_every_line_in_its_text():
    pdf, pages, _ = render.render(RESUME, "resume")
    assert pdf.startswith(b"%PDF-") and pages == 1 == len(PdfReader(io.BytesIO(pdf)).pages)
    printed = " ".join(text(pdf).split()).casefold()  # the name and headings print in caps
    for line in lines(RESUME):
        assert " ".join(line.split()).casefold() in printed


def test_a_letter_keeps_each_line_its_own_line():
    pdf, pages, _ = render.render(LETTER, "cover-letter")
    assert pages == 1
    assert text(pdf).splitlines()[-2:] == ["Cheers,", "Arya"]  # Markdown alone would join them


def test_the_resumes_first_line_is_its_name_in_caps_and_the_contact_line_stays_below():
    pdf = render.render(RESUME, "resume").pdf
    assert [" ".join(line.split()) for line in text(pdf).splitlines()[:2]] == [
        "ARYA STARK",
        "arya.stark@example.com | Columbus, OH",
    ]


def test_the_name_and_contact_line_are_centered_and_the_rest_is_not():
    page = PdfReader(io.BytesIO(render.render(RESUME, "resume").pdf)).pages[0]
    starts = {}
    page.extract_text(visitor_text=lambda t, cm, tm, *_: t.strip() and starts.setdefault(t.strip(), cm[4]))
    width = float(page.mediabox.width)
    for head in ("ARYA STARK", "arya.stark@example.com"):
        assert starts[next(k for k in starts if k.startswith(head))] > width / 6
    assert starts["EXPERIENCE"] == pytest.approx(0.8 * 72)


def test_markup_characters_print_as_written():
    draft = 'Sam Lee\nsam_lee@example.com #1 a*b c_d <e 5 < 10 $5 -- --- "quoted" [@ref]\n'
    for kind in ("resume", "cover-letter"):
        printed = text(render.render(draft, kind)[0])
        assert 'sam_lee@example.com #1 a*b c_d <e 5 < 10 $5 -- --- "quoted" [@ref]' in printed


@pytest.mark.parametrize(
    "planted",
    [
        "<!--raw-typst #text[RAN] -->",
        '<!--raw-typst #read("/etc/passwd") -->',
        '<!--raw-typst #import "@preview/cetz:0.3.0" -->',
    ],
)
def test_raw_typst_in_a_draft_is_never_run(planted):
    pdf = render.render(f"Sam Lee\n\n{planted}\n\nAfter.\n", "resume").pdf
    printed = text(pdf)
    assert "RAN" not in printed and "root:" not in printed and "After." in printed


def test_typst_code_in_a_draft_prints_as_text():
    pdf = render.render('Sam Lee\n\n#read("/etc/passwd") #eval("1+1")\n', "resume").pdf
    printed = text(pdf)
    assert '#read("/etc/passwd") #eval("1+1")' in printed and "root:" not in printed


@pytest.mark.parametrize(
    "planted",
    [
        "![x](/etc/passwd)",
        '<img src="draft.md">',
        "![x](resume.typ)",
        '<a href="#nowhere">here</a>',
        "[there](#nowhere)",
    ],
)
def test_images_and_links_to_labels_neither_read_a_file_nor_stop_the_pdf(planted):
    pdf = render.render(f"Sam Lee\n\n{planted} After.\n", "resume").pdf
    assert "After." in text(pdf)


def test_a_web_link_stays_a_link():
    pdf = render.render("Sam Lee\n\n[LinkedIn](https://www.linkedin.com/in/example)\n", "resume").pdf
    annots = PdfReader(io.BytesIO(pdf)).pages[0]["/Annots"]
    assert [a.get_object()["/A"]["/URI"] for a in annots] == ["https://www.linkedin.com/in/example"]


@pytest.mark.parametrize(
    "dest", ["javascript:alert(1)", "file:///etc/passwd", "http://plain.example", "data:text/html,x"]
)
def test_a_link_that_is_not_https_prints_as_its_text_only(dest):
    pdf = render.render(f"Sam Lee\n\n[Portfolio]({dest}) After.\n", "resume").pdf
    assert "/Annots" not in PdfReader(io.BytesIO(pdf)).pages[0]
    assert "Portfolio After." in text(pdf)


def test_a_resume_is_set_in_gelasio_and_a_letter_in_plex_and_nothing_else():
    assert fonts(render.render(RESUME, "resume").pdf) == {"Gelasio-Regular", "Gelasio-Bold"}
    assert fonts(render.render(LETTER + "\n**Bold**\n", "cover-letter").pdf) == {"IBMPlexSans", "IBMPlexSans-Bold"}


def test_the_same_draft_gives_the_same_bytes():
    assert render.render(RESUME, "resume")[0] == render.render(RESUME, "resume")[0]


def test_a_long_resume_says_how_many_pages():
    assert render.render(RESUME + "\n" + "\n".join(f"- Made-up bullet {n}" for n in range(120)), "resume").pages == 3


@pytest.mark.parametrize("over", [1, 4])
def test_a_resume_just_over_a_page_says_how_many_lines_are_on_the_second(over):
    """Bullets one line long each, added until the page is full, then `over` more."""
    one_page = RESUME
    while render.render(one_page + "\n- Made-up bullet", "resume").pages == 1:
        one_page += "\n- Made-up bullet"
    assert render.render(one_page + "\n- Made-up bullet" * over, "resume")[1:] == (2, over)


def test_a_draft_over_the_limit_is_refused():
    with pytest.raises(render.RenderError, match="over 200 KB"):
        render.render("x" * (render.MAX_DRAFT_BYTES + 1), "resume")


def test_a_draft_too_deeply_nested_is_refused_with_a_reason():
    with pytest.raises(render.RenderError, match="Could not make the PDF: .*depth"):
        render.render(">" * 5000 + " x\n", "resume")


def test_a_compile_that_runs_too_long_is_stopped(monkeypatch):
    monkeypatch.setattr(render, "TIMEOUT_SECONDS", 0.01)
    with pytest.raises(render.RenderError, match="took over 0.01 seconds"):
        render.render(RESUME, "resume")


def test_it_needs_no_network_or_cache(monkeypatch, tmp_path):
    """The child gets an empty package cache; cmarker comes from typst-packages/. No proxy reaches
    anything, so a download would fail."""
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert render.render(RESUME, "resume").pages == 1


def test_prepare_keeps_new_lines_but_not_in_code_and_names_only_a_plain_first_line():
    assert render.prepare("Sam\nsam@x.com\n\n- a\n- b\n", "resume") == {
        "head.md": "# Sam\nsam@x.com\n",
        "draft.md": "\n- a  \n- b\n",
    }
    assert render.prepare("\nSam\n", "resume") == {"head.md": "# Sam\n", "draft.md": ""}
    assert render.prepare("```\na\nb\n```\n", "cover-letter") == {"head.md": "", "draft.md": "```\na\nb\n```\n"}
    assert render.prepare("## Skills\nSQL\n", "resume") == {"head.md": "", "draft.md": "## Skills  \nSQL\n"}
    assert render.prepare("Hi team,\nThanks\n", "cover-letter") == {"head.md": "", "draft.md": "Hi team,  \nThanks\n"}
