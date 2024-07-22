import re
import random

def generate_prompt(template):
    def process_section(match):
        content = match.group(1)
        
        # Check if it's an optional section
        optional_match = re.match(r'0-1\$\$(.*)', content)
        if optional_match:
            content = optional_match.group(1)
            # 50% chance to include the optional section
            if random.random() < 0.5:
                return ''
        
        # Split options and remove any leading/trailing whitespace
        options = [option.strip() for option in content.split('|')]
        return random.choice(options)

    # Use regex to find all sections enclosed in curly braces
    pattern = r'\{([^{}]+)\}'
    return re.sub(pattern, process_section, template)

# Example usage
template = """**{East Asian, Chinese | East Asian, Japanese | East Asian, Korean | South Asian, Indian | Southeast Asian, Thai | Southeast Asian, Filipino | Southeast Asian, Vietnamese | Middle Eastern, Arab | Middle Eastern, Iranian | Middle Eastern, Turkish | Sub-Saharan African, Yoruba | Sub-Saharan African, Zulu | Sub-Saharan African, Igbo | Indigenous American, Native American | Indigenous American, First Nations | European, English | European, German | European, Italian | Pacific Islander, Polynesian | Pacific Islander, Micronesian | Pacific Islander, Melanesian | Afro-Caribbean, Jamaican | Afro-Caribbean, Haitian | Afro-Caribbean, Trinidadian | Indigenous Peoples of the Americas, Inuit | Indigenous Peoples of the Americas, Navajo | Indigenous Peoples of the Americas, Maya | Scandinavian: Swedish | Scandinavian: Norwegian | Scandinavian: Danish | Middle European: German | Middle European: Austrian | Middle European: Czech | South European: Italian | South European: Spanish | South European: Greek } woman wearing {colour block | neon | pink | gold | silver | black | white | floral | pantone | rainbow | unicorn} {0-1$$keyhole | cut-out | small | sexy | tiny | gucci | calvin klein | zara | balenciaga | } {bikini | monokini | wetsuit | zipper swimsuit | keyhole monokini | deep V swimsuit | tankini | suspender swimsuit | bandeau bikini | one shoulder monokini | one piece off shoulder swimsuit} emerging from ocean, {beach | city}, looking over her shoulder, seductive smile,  mystical tropical island, limned lighting, {limned lighting | sunrise | dusk | noon }**"""

print(generate_prompt(template))