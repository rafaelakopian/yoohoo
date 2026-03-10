"""Column name synonyms for auto-mapping.

Maps Student field names to lists of possible header labels (lowercase).
Used by ImportService._auto_map() for fuzzy column matching.
"""

SYNONYMS: dict[str, list[str]] = {
    "full_name": [
        "volledige naam", "full name", "fullname", "naam leerling",
        "naam student", "leerling naam", "student naam",
    ],
    "first_name": [
        "voornaam", "first name", "firstname", "naam", "name",
        "voornaam student", "voornaam leerling",
    ],
    "last_name": [
        "achternaam", "familienaam", "last name", "lastname",
        "achternaam student", "achternaam leerling",
    ],
    "student_number": [
        "leerlingennummer", "leerlingnummer", "studentnummer", "student number",
        "nummer", "nr", "leerling nr", "student nr", "id nummer",
    ],
    "email": [
        "email", "e-mail", "emailadres", "e-mailadres",
        "email student", "e-mail student",
    ],
    "phone": [
        "telefoon", "tel", "phone", "telefoonnummer", "mobiel",
        "telefoon student", "telefoonnummer student",
    ],
    "date_of_birth": [
        "geboortedatum", "geboorte", "date of birth", "dob",
        "geb.datum", "geboortedatum student",
    ],
    "address": [
        "adres", "address", "straat", "street", "adres student",
        "straat en huisnummer", "woonadres",
    ],
    "postal_code": [
        "postcode", "postal code", "zip", "zip code", "postalcode",
        "postcode student",
    ],
    "city": [
        "plaats", "woonplaats", "city", "stad", "gemeente",
        "plaats student",
    ],
    "lesson_day": [
        "lesdag", "dag", "day", "lesson day",
    ],
    "lesson_duration": [
        "lesduur", "duur", "duration", "lesson duration", "minuten",
    ],
    "lesson_time": [
        "lestijd", "tijd", "time", "lesson time", "starttijd",
    ],
    "level": [
        "niveau", "level", "nivo",
    ],
    "notes": [
        "notities", "opmerkingen", "notes", "memo", "opmerking",
    ],
    "invoice_email": [
        "factuur email adres", "factuur e-mail", "factuur email",
        "factuuremailadres", "invoice email", "factuuremail",
        "factuur e-mailadres",
    ],
    "invoice_cc_email": [
        "factuur cc email adres", "factuur cc e-mail", "factuur cc email",
        "factuur cc", "invoice cc email", "cc email", "cc e-mail",
        "factuur cc e-mailadres",
    ],
    "invoice_discount": [
        "factuurkorting", "korting", "discount", "invoice discount",
    ],
    "iban": [
        "iban", "rekeningnummer", "bankrekeningnummer", "bank account",
        "account number",
    ],
    "bic": [
        "bic", "bic code", "swift", "swift code", "bic/swift",
    ],
    "account_holder_name": [
        "naam rekeninghouder", "rekeninghouder", "account holder",
        "account holder name", "tenaamstelling",
    ],
    "account_holder_city": [
        "plaats rekeninghouder", "woonplaats rekeninghouder",
        "account holder city",
    ],
    "direct_debit": [
        "incasseren", "incasso", "direct debit", "automatische incasso",
        "sepa incasso", "machtiging",
    ],
    "guardian_name": [
        "ouder", "voogd", "ouder of voogd", "guardian", "ouder/voogd",
        "naam ouder", "naam voogd", "contactpersoon", "contact",
    ],
    "guardian_relationship": [
        "relatie", "relatie ouder", "relatie ouder/voogd",
        "relationship", "guardian relationship",
    ],
    "guardian_phone": [
        "telefoon ouder", "telefoonnummer ouder", "guardian phone",
        "telefoonnummer privé/werk ouder/voogd", "tel ouder",
    ],
    "guardian_phone_work": [
        "telefoon werk", "werk telefoon", "guardian phone work",
        "telefoonnummer werk",
    ],
    "guardian_email": [
        "email ouder", "e-mail ouder", "guardian email",
        "emailadres ouder",
    ],
}
