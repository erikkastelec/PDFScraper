import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pdfSearch",
    version="1.0.0",
    author="Erik Kastelec",
    author_email="erikkastelec@gmail.com",
    description="PDF text and table search",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/erikkastelec/pdfSearch",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
    ],
    python_requires='>=3.6',
)
