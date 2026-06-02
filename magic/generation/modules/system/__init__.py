# -*- coding: utf-8 -*-

from magic.generation.modules.system.templates import SYSTEM_TEMPLATE
from magic.utils.llm import TemplateFormatter

get_sys_prompt = TemplateFormatter(SYSTEM_TEMPLATE)
