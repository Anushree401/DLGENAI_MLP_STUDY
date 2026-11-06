# MLP + DL & GenAI Study Notes

This is a static study-notes site containing two detailed HTML references:

- `MLP_Final_Notes.html` — Machine Learning Practice notes.
- `DL_GenAI_Final_Notes.html` — Deep Learning and Generative AI notes.

`index.html` is the landing page and is the page Vercel serves at the project URL.

## Deploy to Vercel

1. Push this folder to a GitHub repository.
2. In Vercel, select **Add New → Project** and import that repository.
3. Keep the framework preset as **Other**; there is no build command and no output directory.
4. Deploy. Vercel serves `index.html` as the homepage.

The deployment is static. The explanations, code blocks, search, chapter navigation, and documentation links work online. The HTML files can be downloaded from their own pages.

## Execute code locally

The editable Python cells intentionally run only through the local loopback server:

```bash
python3 serve_notes.py
```

Then open the local URL printed in the terminal. The runner uses the Python environment where it is started, so that environment needs the libraries used in the cells: NumPy, Pandas, Matplotlib, scikit-learn, and PyTorch.

Vercel should not be used to execute arbitrary editable Python submitted from a webpage. Its static deployment is for reading and sharing the notes.
