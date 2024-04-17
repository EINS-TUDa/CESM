from setuptools import setup, find_packages

setup(
    name='cesm',
    version='0.0.1',
    packages=find_packages(),
    package_data={
        'cesm': ['Data/*'],
    },
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
    description='Compact Energy System Modeling Tool',
    url='https://github.com/EINS-TUDa/CESM',
    license='MIT',
)