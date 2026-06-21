#!/bin/bash
# Helper script to run the cold data gatherer for cafes in Jaksel (Jakarta Selatan)

echo "Gathering all cafes in Jakarta Selatan (Jaksel)..."
python3 gather_cold_data.py -q cafe -r "Jakarta Selatan" -o jaksel_cafes

echo ""
echo "Done! The following files have been created:"
echo "  - jaksel_cafes.xml (For structured XML / Excel import)"
echo "  - jaksel_cafes.csv (For direct opening in Excel)"
echo ""
echo "Showing the first few lines of the CSV data:"
head -n 5 jaksel_cafes.csv
