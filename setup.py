from setuptools import setup, find_packages

setup(
    name='cesm',
    version='0.0.8',
    packages=find_packages(),
    description='Compact Energy System Modeling Tool (CESM)',
    long_description="""
Compact Energy System Modeling Tool (CESM)
This is a compact energy system modeling tool that can model different forms of energy carriers and the conversion processes that convert them to each other. 
The optimal output of the model determines how much should be invested in each part of the energy system to meet the energy demand and minimize costs.

An example of the German energy system is also provided. The results of the model are compatible with the results of the paper "Barbosa, Julia, Christopher Ripp, and Florian Steinke. Accessible Modeling of the German Energy Transition: An Open, Compact, and Validated Model. Energies 14, no. 23 (2021)"
    """,
    package_data={
        'cesm': ['Data/*'],
    },
    long_description_content_type='text/markdown',
    py_modules=['cesm'],  # Assuming cesm.py is in the root of your package directory
    entry_points={
        'console_scripts': [
            'cesm = cesm:app',  # Assuming your main function is named main
        ],
    },
    install_requires=[
        "setuptools",
        "openpyxl",
        "numpy",
        "scipy",
        "pandas",
        "gurobipy",
        "plotly",
        "kaleido",
        "click",
        "InquirerPy",
        "pyarrow"
    ],
    # Metadata
    author=['Sina Hajikazemi','Julia Barbosa'],
    author_email='sina.hkazemi@email.com',
    url='https://github.com/EINS-TUDa/CESM',
    license='MIT',
)