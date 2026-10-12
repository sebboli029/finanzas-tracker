"""Configuración de la app — ajustá esto para adaptarla a otra persona."""

# Moneda en la que se muestran y guardan todos los montos de la app, incluidos
# los precios de cripto y acciones que el usuario carga a mano en la Zona de
# inversión. Lo único que se convierte es el monto de monedas extranjeras, con
# la tasa que se trae hacia esta moneda.
MONEDA_BASE = "USD"

FORMATOS_MONEDA = {
    "USD": {"simbolo": "$", "separador_miles": ",", "decimales": 0},
    "EUR": {"simbolo": "€", "separador_miles": ".", "decimales": 0},
    "GBP": {"simbolo": "£", "separador_miles": ",", "decimales": 0},
    "COP": {"simbolo": "$", "separador_miles": ".", "decimales": 0},
}
