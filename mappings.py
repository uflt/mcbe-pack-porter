# -*- coding: utf-8 -*-
"""
Таблицы соответствия имён текстур Java <-> Bedrock.

Что не найдено в таблицах — переносится под тем же именем (у многих блоков и предметов
имена совпадают). Если для какого-то блока/предмета имя неверное — просто допишите его
в BLOCKS_EXTRA / ITEMS_EXTRA ниже (ключ — имя в Java, значение — имя в Bedrock).
"""

# (имя в Java, имя в Bedrock)
COLORS = [
    ("white", "white"), ("orange", "orange"), ("magenta", "magenta"),
    ("light_blue", "light_blue"), ("yellow", "yellow"), ("lime", "lime"),
    ("pink", "pink"), ("gray", "gray"), ("light_gray", "silver"),
    ("cyan", "cyan"), ("purple", "purple"), ("blue", "blue"),
    ("brown", "brown"), ("green", "green"), ("red", "red"), ("black", "black"),
]
WOODS = [
    ("oak", "oak"), ("spruce", "spruce"), ("birch", "birch"),
    ("jungle", "jungle"), ("acacia", "acacia"), ("dark_oak", "big_oak"),
]

BLOCKS_EXTRA = {
    # земля и камень
    "grass_block_top": "grass_top",
    "grass_block_side": "grass_side",
    "grass_block_snow": "grass_side_snowed",
    "farmland": "farmland_dry",
    "farmland_moist": "farmland_wet",
    "mossy_cobblestone": "cobblestone_mossy",
    "stone_bricks": "stonebrick",
    "mossy_stone_bricks": "stonebrick_mossy",
    "cracked_stone_bricks": "stonebrick_cracked",
    "chiseled_stone_bricks": "stonebrick_carved",
    "granite": "stone_granite",
    "polished_granite": "stone_granite_smooth",
    "diorite": "stone_diorite",
    "polished_diorite": "stone_diorite_smooth",
    "andesite": "stone_andesite",
    "polished_andesite": "stone_andesite_smooth",
    "bricks": "brick",
    "nether_bricks": "nether_brick",
    "red_nether_bricks": "red_nether_brick",
    "end_stone_bricks": "end_bricks",
    "terracotta": "hardened_clay",
    "slime_block": "slime",
    "wet_sponge": "sponge_wet",
    # песчаник
    "sandstone": "sandstone_normal",
    "chiseled_sandstone": "sandstone_carved",
    "cut_sandstone": "sandstone_smooth",
    "red_sandstone": "red_sandstone_normal",
    "chiseled_red_sandstone": "red_sandstone_carved",
    "cut_red_sandstone": "red_sandstone_smooth",
    # кварц
    "chiseled_quartz_block": "quartz_block_chiseled",
    "chiseled_quartz_block_top": "quartz_block_chiseled_top",
    "quartz_pillar": "quartz_block_lines",
    "quartz_pillar_top": "quartz_block_lines_top",
    "nether_quartz_ore": "quartz_ore",
    # функциональные блоки
    "furnace_front": "furnace_front_off",
    "dispenser_front": "dispenser_front_horizontal",
    "dropper_front": "dropper_front_horizontal",
    "carved_pumpkin": "pumpkin_face_off",
    "jack_o_lantern": "pumpkin_face_on",
    "redstone_lamp": "redstone_lamp_off",
    "note_block": "noteblock",
    "spawner": "mob_spawner",
    "torch": "torch_on",
    "redstone_torch": "redstone_torch_on",
    "cobweb": "web",
    "dead_bush": "deadbush",
    "sugar_cane": "reeds",
    # рельсы
    "rail": "rail_normal",
    "rail_corner": "rail_normal_turned",
    "powered_rail": "rail_golden",
    "powered_rail_on": "rail_golden_powered",
    "detector_rail": "rail_detector",
    "detector_rail_on": "rail_detector_powered",
    "activator_rail": "rail_activator",
    "activator_rail_on": "rail_activator_powered",
    # цветы
    "dandelion": "flower_dandelion",
    "poppy": "flower_rose",
    "blue_orchid": "flower_blue_orchid",
    "allium": "flower_allium",
    "azure_bluet": "flower_houstonia",
    "red_tulip": "flower_tulip_red",
    "orange_tulip": "flower_tulip_orange",
    "white_tulip": "flower_tulip_white",
    "pink_tulip": "flower_tulip_pink",
    "oxeye_daisy": "flower_oxeye_daisy",
    # двери и люки
    "iron_door_top": "door_iron_upper",
    "iron_door_bottom": "door_iron_lower",
    "oak_trapdoor": "trapdoor",
}

ITEMS_EXTRA = {
    # еда
    "beef": "beef_raw", "cooked_beef": "beef_cooked",
    "porkchop": "porkchop_raw", "cooked_porkchop": "porkchop_cooked",
    "chicken": "chicken_raw", "cooked_chicken": "chicken_cooked",
    "mutton": "mutton_raw", "cooked_mutton": "mutton_cooked",
    "rabbit": "rabbit_raw", "cooked_rabbit": "rabbit_cooked",
    "cod": "fish_cod_raw", "cooked_cod": "fish_cod_cooked",
    "salmon": "fish_salmon_raw", "cooked_salmon": "fish_salmon_cooked",
    "tropical_fish": "fish_clownfish_raw", "pufferfish": "fish_pufferfish_raw",
    "baked_potato": "potato_baked", "poisonous_potato": "potato_poisonous",
    "golden_apple": "apple_golden", "enchanted_golden_apple": "appleEnchanted",
    "golden_carrot": "carrot_golden", "glistering_melon_slice": "melon_speckled",
    "melon_slice": "melon",
    # ведра
    "bucket": "bucket_empty", "water_bucket": "bucket_water",
    "lava_bucket": "bucket_lava", "milk_bucket": "bucket_milk",
    "powder_snow_bucket": "bucket_powder_snow", "cod_bucket": "bucket_cod",
    "salmon_bucket": "bucket_salmon", "pufferfish_bucket": "bucket_pufferfish",
    "tropical_fish_bucket": "bucket_tropical",
    # материалы и прочее
    "slime_ball": "slimeball", "redstone": "redstone_dust",
    "book": "book_normal", "enchanted_book": "book_enchanted",
    "writable_book": "book_writable", "written_book": "book_written",
    "bow": "bow_standby", "fishing_rod": "fishing_rod_uncast",
    "map": "map_empty", "filled_map": "map_filled",
    "wheat_seeds": "seeds_wheat", "pumpkin_seeds": "seeds_pumpkin",
    "melon_seeds": "seeds_melon", "beetroot_seeds": "seeds_beetroot",
    "glass_bottle": "potion_bottle_empty", "potion": "potion_bottle_drinkable",
    "splash_potion": "potion_bottle_splash", "totem_of_undying": "totem",
    "scute": "turtle_shell_piece", "firework_rocket": "fireworks",
    "firework_star": "fireworks_charge",
    "minecart": "minecart_normal", "chest_minecart": "minecart_chest",
    "furnace_minecart": "minecart_furnace", "hopper_minecart": "minecart_hopper",
    "tnt_minecart": "minecart_tnt", "command_block_minecart": "minecart_command_block",
    "oak_door": "door_wood", "iron_door": "door_iron",
    "oak_sign": "sign",
    # пластинки
    "music_disc_13": "record_13", "music_disc_cat": "record_cat",
    "music_disc_blocks": "record_blocks", "music_disc_chirp": "record_chirp",
    "music_disc_far": "record_far", "music_disc_mall": "record_mall",
    "music_disc_mellohi": "record_mellohi", "music_disc_stal": "record_stal",
    "music_disc_strad": "record_strad", "music_disc_ward": "record_ward",
    "music_disc_11": "record_11", "music_disc_wait": "record_wait",
    "music_disc_pigstep": "record_pigstep", "music_disc_otherside": "record_otherside",
    # красители (в Bedrock у старых/новых красителей разные файлы)
    "bone_meal": "dye_powder_white", "lapis_lazuli": "dye_powder_blue",
    "ink_sac": "dye_powder_black", "cocoa_beans": "dye_powder_brown",
    "white_dye": "dye_powder_white_new", "blue_dye": "dye_powder_blue_new",
    "black_dye": "dye_powder_black_new", "brown_dye": "dye_powder_brown_new",
}

# материалы брони: Java -> Bedrock (для файлов моделей брони)
ARMOR = {
    "leather": "leather", "chainmail": "chain", "iron": "iron",
    "gold": "gold", "diamond": "diamond", "netherite": "netherite",
    "turtle": "turtle",
}


def _build_blocks():
    m = {}
    for j, b in COLORS:
        m[f"{j}_wool"] = f"wool_colored_{b}"
        m[f"{j}_terracotta"] = f"hardened_clay_stained_{b}"
        m[f"{j}_stained_glass"] = f"glass_{b}"
        m[f"{j}_stained_glass_pane_top"] = f"glass_pane_top_{b}"
        m[f"{j}_concrete"] = f"concrete_{b}"
        m[f"{j}_concrete_powder"] = f"concrete_powder_{b}"
        m[f"{j}_glazed_terracotta"] = f"glazed_terracotta_{b}"
    for j, b in WOODS:
        m[f"{j}_planks"] = f"planks_{b}"
        m[f"{j}_log"] = f"log_{b}"
        m[f"{j}_log_top"] = f"log_{b}_top"
        m[f"{j}_leaves"] = f"leaves_{b}"
        m[f"{j}_sapling"] = "sapling_roofed_oak" if b == "big_oak" else f"sapling_{b}"
        door = "wood" if j == "oak" else j
        m[f"{j}_door_top"] = f"door_{door}_upper"
        m[f"{j}_door_bottom"] = f"door_{door}_lower"
    m.update(BLOCKS_EXTRA)
    return m


def _build_items():
    m = {}
    for tool in ("sword", "pickaxe", "axe", "shovel", "hoe"):
        m[f"wooden_{tool}"] = f"wood_{tool}"
        m[f"golden_{tool}"] = f"gold_{tool}"
    for piece in ("helmet", "chestplate", "leggings", "boots"):
        m[f"golden_{piece}"] = f"gold_{piece}"
    for j, b in COLORS:
        if j in ("white", "blue", "black", "brown"):
            continue  # эти красители заданы вручную выше
        m[f"{j}_dye"] = f"dye_powder_{b}"
    for j, _ in WOODS:
        if j != "oak":
            m[f"{j}_door"] = f"door_{j}"
    m.update(ITEMS_EXTRA)
    return m


def _invert(d):
    out = {}
    for k, v in d.items():
        out.setdefault(v, k)
    return out


JAVA_TO_BEDROCK_BLOCKS = _build_blocks()
JAVA_TO_BEDROCK_ITEMS = _build_items()
BEDROCK_TO_JAVA_BLOCKS = _invert(JAVA_TO_BEDROCK_BLOCKS)
BEDROCK_TO_JAVA_ITEMS = _invert(JAVA_TO_BEDROCK_ITEMS)
BEDROCK_TO_JAVA_ARMOR = {v: k for k, v in ARMOR.items()}
