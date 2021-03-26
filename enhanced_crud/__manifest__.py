# -*- coding: utf-8 -*-
###################################################################################
#    Author: Bluisknot (bluisknot@gmail.com)
#
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###################################################################################

{
    "name": "Enhanced CRUD",
    "version": "12.0.0",
    "summary": "The Odoo CRUD operations presented in a different way",
    "description": """
Enhanced CRUD
==========
The Odoo CRUD operations presented in a different way and more

Key Features
------------
* Form Views in a new window
* New List and Kanban View pager and contextual menu
* Configuration options to prevent you from having to modify your code
    """,
    "category": "Extra Tools",
    "author": "Bluisknot (bluisknot@gmail.com)",
    "depends": ["base"],
    "data": [
        "security/enhanced_crud.xml",
        "security/ir.model.access.csv",
        "views/enhanced_crud_settings.xml",
        "templates/enhanced_crud.xml",
        "views/enhanced_crud.xml",
        "data/enhanced_crud.xml",
        "wizards/enhanced_crud.xml",
    ],
    "qweb": ["static/src/xml/enhanced_crud.xml"],
    "installable": True,
    "license": "LGPL-3",
}
