{
    "name": "Code Generator - geoengine",
    "version": "12.0.0",
    "summary": "Code Generator - Manage geoengine",
    "description": "Code generator builder to manage geoengine",
    "author": "Mathben (mathben@technolibre.ca)",
    "category": "Extra Tools",
    "depends": [
        "code_generator",
        "base_geoengine",
    ],
    "installable": True,
    "data": [
        "wizards/code_generator_generate_views_wizard.xml",
    ],
    "post_init_hook": "post_init_hook",
}
