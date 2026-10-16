from datetime import date

from gnc_lite.config import AppConfig, Profile, load_config, save_config
from gnc_lite.domain.money import Money


def test_default_config_e_pessoal():
    config = AppConfig()
    assert config.profile is Profile.PERSONAL
    assert config.mei_limite_anual == Money.from_decimal("81000.00")


def test_round_trip_json(tmp_path):
    path = tmp_path / "config.json"
    config = AppConfig(
        profile=Profile.MEI,
        mei_nome_empresarial="Padaria do Ze MEI",
        mei_cnpj="12.345.678/0001-99",
        mei_atividade="Comercio de panificados",
        mei_municipio="Campinas",
        mei_uf="SP",
        mei_inicio_atividade=date(2026, 3, 15),
        mei_limite_anual=Money.from_decimal("81000.00"),
    )
    save_config(config, path)
    loaded = load_config(path)

    assert loaded.profile is Profile.MEI
    assert loaded.mei_nome_empresarial == "Padaria do Ze MEI"
    assert loaded.mei_cnpj == "12.345.678/0001-99"
    assert loaded.mei_inicio_atividade == date(2026, 3, 15)
    assert loaded.mei_limite_anual == Money.from_decimal("81000.00")


def test_load_inexistente_usa_padroes(tmp_path):
    config = load_config(tmp_path / "nao_existe.json")
    assert config.profile is Profile.PERSONAL
    assert config.mei_inicio_atividade is None


def test_load_arquivo_invalido_usa_padroes(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ isso nao e json", encoding="utf-8")
    assert load_config(path).profile is Profile.PERSONAL
