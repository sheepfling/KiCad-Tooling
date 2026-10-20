"""Source manifest and digests for synthetic connector native fixtures."""

from __future__ import annotations

from pathlib import Path


def connector_return_fixture_sources(fixture_root: Path) -> dict[str, Path]:
    """Return the named, tooling-owned connector fixture sources."""
    return {
        "fault": fixture_root / "cohort-connector-ground-domains/fault.kicad_sch",
        "control": fixture_root / "cohort-connector-ground-domains/control.kicad_sch",
        "return-positive-rail-fault": fixture_root / "return-pin-positive-rail/fault.kicad_sch",
        "return-positive-rail-control": fixture_root / "return-pin-positive-rail/control.kicad_sch",
        "cross-symbol-fault": fixture_root
        / "cohort-cross-symbol-connectors/cross-symbol-fault.kicad_sch",
        "cross-symbol-control": fixture_root
        / "cohort-cross-symbol-connectors/cross-symbol-control.kicad_sch",
        "cross-symbol-open": fixture_root
        / "cohort-cross-symbol-connectors/cross-symbol-open.kicad_sch",
        "mapped-supply-fault": fixture_root
        / "cohort-mapped-connector-supplies/split-supply-fault.kicad_sch",
        "mapped-supply-control": fixture_root
        / "cohort-mapped-connector-supplies/common-supply-control.kicad_sch",
        "channel-power-fault": fixture_root / "cohort-channel-power-names/fault.kicad_sch",
        "channel-power-control": fixture_root / "cohort-channel-power-names/control.kicad_sch",
        "four-db9-fault": fixture_root / "four-port-db9-returns/fault.kicad_sch",
        "four-db9-control": fixture_root / "four-port-db9-returns/control.kicad_sch",
        "four-db9-pwm-fault": fixture_root / "four-port-db9-returns/pwm-fault.kicad_sch",
        "four-db9-pwm-control": fixture_root / "four-port-db9-returns/pwm-control.kicad_sch",
        "four-db9-neutral-fault": fixture_root
        / "four-port-db9-returns/numeric-function-neutral-fault.kicad_sch",
        "four-db9-neutral-control": fixture_root
        / "four-port-db9-returns/numeric-function-neutral-control.kicad_sch",
        "ret-numbered-fault": fixture_root / "four-port-db9-returns/ret-numbered-fault.kicad_sch",
        "ret-unindexed-fault": fixture_root / "four-port-db9-returns/ret-unindexed-fault.kicad_sch",
        "ret-control": fixture_root / "four-port-db9-returns/ret-control.kicad_sch",
        "peer-power-fault": fixture_root / "generic-peer-power-pin/fault.kicad_sch",
        "peer-power-control": fixture_root / "generic-peer-power-pin/control.kicad_sch",
        "peer-pin-outlier-fault": fixture_root
        / "generic-peer-pin-assignment-native/fault.kicad_sch",
        "peer-pin-outlier-control": fixture_root
        / "generic-peer-pin-assignment-native/control.kicad_sch",
        "peer-pin-part-id-open-fault": fixture_root
        / "connector-peer-part-id-native/fault.kicad_sch",
        "part-id-all-open-generic-peer-fault": fixture_root
        / "connector-peer-part-id-native/all-open-generic-fault.kicad_sch",
        "peer-pin-part-id-common-control": fixture_root
        / "connector-peer-part-id-native/control.kicad_sch",
        "peer-pin-part-id-split-fault": fixture_root
        / "connector-peer-part-id-native/split-assignment-fault.kicad_sch",
        "footprint-alias-fault": fixture_root / "connector-footprint-alias-native/fault.kicad_sch",
        "footprint-alias-control": fixture_root
        / "connector-footprint-alias-native/control.kicad_sch",
        "footprint-alias-open-fault": fixture_root
        / "connector-footprint-alias-native/open-fault.kicad_sch",
        "footprint-alias-all-open-fault": fixture_root
        / "connector-footprint-alias-native/all-open-fault.kicad_sch",
        "footprint-alias-numeric-fault": fixture_root
        / "connector-footprint-alias-native/numeric-fault.kicad_sch",
        "footprint-alias-numeric-control": fixture_root
        / "connector-footprint-alias-native/numeric-control.kicad_sch",
        "footprint-alias-numeric-open-fault": fixture_root
        / "connector-footprint-alias-native/numeric-open-fault.kicad_sch",
        "footprint-alias-named-power-input-fault": fixture_root
        / "connector-footprint-named-power-input-native/fault.kicad_sch",
        "footprint-alias-named-power-input-control": fixture_root
        / "connector-footprint-named-power-input-native/control.kicad_sch",
        "footprint-alias-named-signal-input-fault": fixture_root
        / "connector-footprint-named-signal-input-native/fault.kicad_sch",
        "footprint-alias-named-signal-input-control": fixture_root
        / "connector-footprint-named-signal-input-native/control.kicad_sch",
        "footprint-alias-named-power-output-fault": fixture_root
        / "connector-footprint-named-power-output-native/fault.kicad_sch",
        "footprint-alias-named-power-output-control": fixture_root
        / "connector-footprint-named-power-output-native/control.kicad_sch",
        "footprint-alias-named-signal-output-fault": fixture_root
        / "connector-footprint-named-signal-output-native/fault.kicad_sch",
        "footprint-alias-named-signal-output-control": fixture_root
        / "connector-footprint-named-signal-output-native/control.kicad_sch",
        "footprint-alias-named-signal-divergence-fault": fixture_root
        / "connector-footprint-named-signal-divergence-native/fault.kicad_sch",
        "footprint-alias-named-power-input-divergence-fault": fixture_root
        / "connector-footprint-named-power-input-divergence-native/fault.kicad_sch",
        "footprint-alias-named-power-input-divergence-control": fixture_root
        / "connector-footprint-named-power-input-divergence-native/control.kicad_sch",
        "footprint-alias-named-power-input-all-open-fault": fixture_root
        / "connector-footprint-named-power-input-all-open-native/fault.kicad_sch",
        "footprint-alias-named-power-input-all-open-control": fixture_root
        / "connector-footprint-named-power-input-all-open-native/control.kicad_sch",
        "footprint-alias-named-power-output-divergence-fault": fixture_root
        / "connector-footprint-named-power-output-divergence-native/fault.kicad_sch",
        "footprint-alias-named-power-output-divergence-control": fixture_root
        / "connector-footprint-named-power-output-divergence-native/control.kicad_sch",
        "peer-pin-minority-fault": fixture_root
        / "generic-peer-pin-assignment-native/minority-fault.kicad_sch",
        "peer-pin-divergence-fault": fixture_root
        / "generic-peer-pin-assignment-native/divergence-fault.kicad_sch",
        "generic-placeholder-divergence-fault": fixture_root
        / "generic-peer-pin-assignment-native/generic-placeholder-divergence-fault.kicad_sch",
        "peer-scope-split-return-fault": fixture_root
        / "generic-peer-pin-assignment-native/peer-scope-split-return-fault.kicad_sch",
        "generic-placeholder-control": fixture_root
        / "generic-peer-pin-assignment-native/generic-placeholder-control.kicad_sch",
        "two-peer-open-fault": fixture_root
        / "generic-peer-pin-assignment-native/two-peer-open-fault.kicad_sch",
        "two-peer-no-connect-fault": fixture_root
        / "generic-peer-pin-assignment-native/two-peer-no-connect-fault.kicad_sch",
        "two-peer-common-control": fixture_root
        / "generic-peer-pin-assignment-native/two-peer-common-control.kicad_sch",
        "all-open-generic-peer-fault": fixture_root
        / "generic-peer-pin-all-open-native/fault.kicad_sch",
        "all-open-generic-peer-control": fixture_root
        / "generic-peer-pin-all-open-native/control.kicad_sch",
        "all-open-generic-signal-peer-fault": fixture_root
        / "generic-peer-signal-pin-all-open-native/fault.kicad_sch",
        "all-open-generic-signal-peer-control": fixture_root
        / "generic-peer-signal-pin-all-open-native/control.kicad_sch",
        "all-open-generic-signal-types-fault": fixture_root
        / "generic-peer-signal-pin-types-native/fault.kicad_sch",
        "all-open-generic-signal-types-control": fixture_root
        / "generic-peer-signal-pin-types-native/control.kicad_sch",
        "single-offboard-port-control": fixture_root
        / "generic-peer-pin-assignment-native/single-offboard-port-control.kicad_sch",
        "unconnected-generic-power-input-fault": fixture_root
        / "unconnected-generic-power-input-connector/fault.kicad_sch",
        "unconnected-generic-power-input-control": fixture_root
        / "unconnected-generic-power-input-connector/control.kicad_sch",
        "unconnected-named-supply-fault": fixture_root
        / "unconnected-named-connector-pins/supply-fault.kicad_sch",
        "unconnected-named-return-fault": fixture_root
        / "unconnected-named-connector-pins/return-fault.kicad_sch",
        "unconnected-named-power-control": fixture_root
        / "unconnected-named-connector-pins/control.kicad_sch",
        "unconnected-named-component-supply-fault": fixture_root
        / "unconnected-named-component-pins/supply-fault.kicad_sch",
        "unconnected-named-component-return-fault": fixture_root
        / "unconnected-named-component-pins/return-fault.kicad_sch",
        "unconnected-named-component-power-control": fixture_root
        / "unconnected-named-component-pins/control.kicad_sch",
        "unconnected-generic-component-power-input-fault": fixture_root
        / "generic-component-power-input/fault.kicad_sch",
        "unconnected-generic-component-power-input-control": fixture_root
        / "generic-component-power-input/control.kicad_sch",
        "unconnected-generic-component-power-input-no-connect-fault": fixture_root
        / "generic-component-power-input/no-connect-fault.kicad_sch",
        "unconnected-generic-component-power-input-dnp-control": fixture_root
        / "generic-component-power-input/dnp-control.kicad_sch",
        "peer-generic-power-input-fault": fixture_root
        / "generic-peer-power-input-assignment/fault.kicad_sch",
        "peer-generic-power-input-control": fixture_root
        / "generic-peer-power-input-assignment/control.kicad_sch",
        "peer-named-power-input-open-fault": fixture_root
        / "named-peer-power-input-open/fault.kicad_sch",
        "peer-named-power-input-open-control": fixture_root
        / "named-peer-power-input-open/control.kicad_sch",
        "peer-named-power-input-divergence-fault": fixture_root
        / "named-peer-power-input-divergence/fault.kicad_sch",
        "peer-named-power-input-divergence-control": fixture_root
        / "named-peer-power-input-divergence/control.kicad_sch",
        "peer-named-power-input-all-open-fault": fixture_root
        / "named-peer-power-input-all-open/fault.kicad_sch",
        "peer-named-power-input-all-open-control": fixture_root
        / "named-peer-power-input-all-open/control.kicad_sch",
        "connector-named-power-input-open-fault": fixture_root
        / "connector-named-power-input-peer-native/fault.kicad_sch",
        "connector-named-power-input-open-control": fixture_root
        / "connector-named-power-input-peer-native/control.kicad_sch",
        "connector-named-power-input-all-open-fault": fixture_root
        / "connector-named-power-input-peer-native/all-open-fault.kicad_sch",
        "connector-named-power-input-divergent-fault": fixture_root
        / "connector-named-power-input-peer-native/divergent-fault.kicad_sch",
        "connector-named-power-output-open-fault": fixture_root
        / "connector-named-power-output-peer-native/fault.kicad_sch",
        "connector-named-power-output-open-control": fixture_root
        / "connector-named-power-output-peer-native/control.kicad_sch",
        "connector-named-power-output-all-open-fault": fixture_root
        / "connector-named-power-output-peer-native/all-open-fault.kicad_sch",
        "connector-named-power-output-divergent-fault": fixture_root
        / "connector-named-power-output-peer-native/divergent-fault.kicad_sch",
        "component-peer-assignment-outlier-fault": fixture_root
        / "generic-component-peer-pin-assignment-outlier/fault.kicad_sch",
        "component-peer-assignment-outlier-control": fixture_root
        / "generic-component-peer-pin-assignment-outlier/control.kicad_sch",
    }


CONNECTOR_RETURN_FIXTURE_SOURCE_HASHES = {
    "fault": "aea557c738a417192ccfce0e7228b5832aab566f66c2a354dce72f5df7882474",
    "control": "9584fbcc1f0560ac66306691f49d161617199b240cb7520588ad298a69b72176",
    "return-positive-rail-fault": "1837bf8f8cec031d5dff5fb7ddb65ad59f87fdf7aa80706d142b969c7fc8a967",
    "return-positive-rail-control": "9584fbcc1f0560ac66306691f49d161617199b240cb7520588ad298a69b72176",
    "cross-symbol-fault": "941aa1acc62384d86fe04e7dec77638a5e23cd8b67b196bc1d93130e5e99f21e",
    "cross-symbol-control": "5b9f1a9d18b4e57495d090e815ff192c44f61b8a164ef03622e3d962ac553baf",
    "cross-symbol-open": "180c28fd280b71febe0c636e799217f0d86a3659c45e280cb86a768b7a03533a",
    "mapped-supply-fault": "0991c6df2403df88ff33d5c359b14487b6aa385023bd864573ce236478449213",
    "mapped-supply-control": "c45d390f138ebb9e440a1c6b0fea822f858ce9e31bfa229b28aaddc248adca3b",
    "channel-power-fault": "d6a52dd120801e0bf5776e82421ceb64670b26a9ace28afafd89b608a61aabb3",
    "channel-power-control": "37c7c28963b530a679cd3dc2087a4fa3b5d97dda52250332556406c66b9e1fc7",
    "four-db9-fault": "1baabede29ea7a33cf85ec85f35c3affb2937e31db981e8f5d68f3b769d43791",
    "four-db9-control": "ed2096c8aedbf263290c19c3a067cdf959fac92512aa3ab02fabbd7e10db4171",
    "four-db9-pwm-fault": "c4a842c1685d5fbf21985aa22bd0b6436e163025f4381a8ac2544621c264e546",
    "four-db9-pwm-control": "3c00cfdee7a7bbba3439baf49f82eb6911ead068cf04ac0782f8f8fe7297cecc",
    "four-db9-neutral-fault": "8b54babacd735da898cbd477b641a57085ff03b74bf0d9aa665fc8625a36f65f",
    "four-db9-neutral-control": "49e3bca48e79e4b46ce4eba8298026b5c730fca56b119a3ec407dfaafbcf54cd",
    "ret-numbered-fault": "254f6b25e897c2bd5f4e7eda254cca4ed9f327d41d2a1b6094ad25dde40132e4",
    "ret-unindexed-fault": "2f3dfe64f45cded7cc24f921882ce6ba472d30f7d6a49a8ebb20d4fbca7e1fc7",
    "ret-control": "7fb0e168dcf55270162327d4480c3dec21dac3c5c80cfc4fe9d3a7f3c3d70efa",
    "peer-power-fault": "4e2382aede1643770a466a9c902b1e960f8a8ab0d1bc676a03db33dfe6e582a8",
    "peer-power-control": "e50d57b2739dc49d3b164e0ea141f48835967fdc1982d3cfdd702f671dc7d197",
    "peer-pin-outlier-fault": "e9945c83c351ece43064a6c09c770fd8f3ab5fadd550ac58ee5d001f5d8842e2",
    "peer-pin-outlier-control": "94a9897ea50645a4232abf005477e620a4cd9b12330dfc2d6f32734e8157b8be",
    "peer-pin-part-id-open-fault": "db6f556278611edb21a66f8445f7dfc3a2e456a63783dc3d1e8a79a56a69d478",
    "part-id-all-open-generic-peer-fault": "156b464b55cc188154c9b724976c976effbf9ec8cf38ff347811a31f9148ee0a",
    "peer-pin-part-id-common-control": "b8b85aa1fdc8c62547eab58788b120fa6028a8ba65051126f954432f4dd07d2c",
    "peer-pin-part-id-split-fault": "8530bab2ac3537a821be48321e9bb713aa8b2933d714902cc5a30fb4168fa192",
    "footprint-alias-fault": "e45b8069603078c1a26198b962b96b20d8a7f9dff39b195b7bb6399e00b323c0",
    "footprint-alias-control": "d5c77a1b8de808ab82c9f98f0172af7f6f933ce43536dabe00c6fbf83e048e28",
    "footprint-alias-open-fault": "ba6fd627b7a8e994ca554dbb9f3a1d67197f8a48d5302c5ee6c78318be424605",
    "footprint-alias-all-open-fault": "798d07bb64d60bbeab73b7203e052ce557e50b6da6453044ec4ccef686f78c27",
    "footprint-alias-numeric-fault": "505a7b2d1eaa74c54d476c5cab9cfcc41649ed51a64f2da4ebd9f5beb6a74f94",
    "footprint-alias-numeric-control": "c8140e9cf9030ccb646121631d186cef97b7d9c76b0d994c2cb3648aaae28a27",
    "footprint-alias-numeric-open-fault": "1a011151f612ba45769e859e0ada0cf67da46dea50d062e0559e4591f537d270",
    "footprint-alias-named-power-input-fault": "cfe8665acc39c84863f5ffa45df9343d0ee94bcfa16baad52223ced344b940ab",
    "footprint-alias-named-power-input-control": "dd864fe4a51950ba0c47d007b682458c37632cb2e84478c2303df926fc9a2ac9",
    "footprint-alias-named-signal-input-fault": "faa41e1882b02ffe9ec3972855c93d63232d6a81ef22a1f21e0827c6ad4f35b4",
    "footprint-alias-named-signal-input-control": "2b5382a50608b644118693641ccbfd4280747d084550e9b5b0201449d2e2c620",
    "footprint-alias-named-power-output-fault": "f4d0b2505410d37a4a5b26598bcdc6b030fab5190290fcbea2690f59142e01b2",
    "footprint-alias-named-power-output-control": "43fcd7e09c75bba6d11b12ce937fd808c4e694b17fc4551769fdccd38abfde29",
    "footprint-alias-named-signal-output-fault": "338f674f9dab065e286b2c5a4495b7967c81947343ce1497fefec347666362c8",
    "footprint-alias-named-signal-output-control": "f072787dbd52dafcc5e2fd0728ed2bc4add23653d8b4978c7472aa658b660d8f",
    "footprint-alias-named-signal-divergence-fault": "2a63cd0836321ce6752b5b4725d830a7f96ad01533e903fe24dfae5b696084a1",
    "footprint-alias-named-power-input-divergence-fault": "d4dfd83d6e8c9859411e613b6f9313ae65efd25c33056541bf35b0e484b70aea",
    "footprint-alias-named-power-input-divergence-control": "8b055617a737dde04b6647a7ce8f5e4a167aa9567b712a1b0d88696eae1f8a7c",
    "footprint-alias-named-power-output-divergence-fault": "4c46589c7cd8b8ef9ec6db778b10c5f7200918b92dfb60c522208dcc24d243b9",
    "footprint-alias-named-power-output-divergence-control": "ca350129168dc67fe71153a59a53d7901c92e413119798463cdca04d96e43482",
    "peer-pin-minority-fault": "a071543178ad7668d20a3653fea5196cf556c3b96338b81dbeac97a6360ede2c",
    "peer-pin-divergence-fault": "c278b2ff86c869a6dba7c19ee08f064a863d282d251be44fd47c1e8a71254e57",
    "generic-placeholder-divergence-fault": "f6f4c9b419ab590366ca329b1ac0749706b29536017f2f24145de7ef6bdfaf30",
    "peer-scope-split-return-fault": "a597bbdee4794b3de8ff08bce5691363a7a123bde303462d64cb692a6a97968e",
    "generic-placeholder-control": "d63a7f7cd79fd0855de599041dacb8219313ffbb2667f37d1e61e88fbec880c0",
    "two-peer-open-fault": "3de502ac74b394afb21cdaef8130026f11f7aa6050018a571dc65b10ae864350",
    "two-peer-no-connect-fault": "8801b0ff24e9f012e6f2df10247cdc04668db40d3233eb5d2111d279cfdf7256",
    "two-peer-common-control": "ae23ddb802c9a0f5cf30e89699a2cf6f48b3d15b6e18967387e756dcdf6fa3df",
    "all-open-generic-peer-fault": "ef324858a679dd53b4207be2abc9a2d2cf90517af9c86a845c52d4604bcdc9cf",
    "all-open-generic-peer-control": "c0cb38abf69437308aba70428c2ef05ae83a51aeb9fab592fe6fef33fb3a0713",
    "all-open-generic-signal-peer-fault": "77adf18dff325f85bf7675d42a25ad1603aa6debb67a96b586646598fac75d37",
    "all-open-generic-signal-peer-control": "144e3e571c2023e4d90048c95fe16f532bcd459c3f5a6e6da6c8b2632282046b",
    "all-open-generic-signal-types-fault": "fbf954e97907913169d53491437423527c404795e1aeb4017ba4c3864c4acd02",
    "all-open-generic-signal-types-control": "b59b67ba4f189afa4cf5e04e38ef54c748003ecde1195ab89d1f9cf52c51f22a",
    "single-offboard-port-control": "ceaa7038e372ec74a00f7e7c2cb5311377df01624760ab555adb413c4e02d8e9",
    "unconnected-generic-power-input-fault": "2e16c602d6ba0068360b3f8b493351f6d7e4d7adbe94946d17db883587f0528f",
    "unconnected-generic-power-input-control": "b05c1a3994a4f26f07e18bdfe28c8caaf4a298cbb66b6d1814b20c9a7dce2c13",
    "unconnected-named-supply-fault": "e4f00aa22957dcdb152cc10a694b25ddeb2d442ed3cd6827bd2e9b2f6cf233aa",
    "unconnected-named-return-fault": "a9a76c8c9a1a01978b3c5ae3228825658631c4c9ad9cc5b73566427f5ce80a5f",
    "unconnected-named-power-control": "ee2980cf387a0326ddb92bcbec8f562ca560c3a9cc9cc249075002148f1e2275",
    "unconnected-named-component-supply-fault": "f1ab42010ec4d41b3ea971e797a7cdff6c020fdaf86e7aae9e2f94664731d18e",
    "unconnected-named-component-return-fault": "43a421486e1ac8f138269128715a45e47fc1998a266d631c8461ffaaf58f9357",
    "unconnected-named-component-power-control": "65e95e66fe3af0ce5136e5763f10f4b3aec71f658f790db929793a45c1895000",
    "unconnected-generic-component-power-input-fault": "40271ae0a6551c8c7209427b30e89d9a95267aa92765eaac1a5cdf65e1ffd1a1",
    "unconnected-generic-component-power-input-control": "67d6ad249e1caa2095b3a408457e6a1710fb9bb6ef7d8e5cb1fdcdd7710b43ec",
    "unconnected-generic-component-power-input-no-connect-fault": "664e619ceaba71c27bd7acfaa0bb4563ab3203b33a03c564b2a8f7c6bdf4c4bd",
    "unconnected-generic-component-power-input-dnp-control": "3be52ef83ba54bf0f43bede043095afe42583319e9fd6fa19f17aba250cc3c81",
    "peer-generic-power-input-fault": "594736519e5c2e3bde88af27d9f059749060014a71f6447aeeceeb8767e7bdae",
    "peer-generic-power-input-control": "9242ac4bf9c466ea0e5a4b41a616c6de881283fdac697ef3e55618040ea6746d",
    "peer-named-power-input-open-fault": "1c9d102a0cac31c7518e52decfd8860fe1d9b39165f27049a6977a21cd92e408",
    "peer-named-power-input-open-control": "ce5553c0a40d57bcc5719089d607ddec91398e20155cbe3cb2edae2d2ee49ed3",
    "peer-named-power-input-divergence-fault": "0adf95fd2320f084c9475d896db2362c2b89123b303c01f3d83b2ebdffabe832",
    "peer-named-power-input-divergence-control": "89842c056127f07240df3e8dc812c8d89e04c1703a07dd247b450886d3b6c727",
    "peer-named-power-input-all-open-fault": "07868167a3fcbe4a8e06a8f7fda29dbc73138808ada53e805db6cab4aa8909fc",
    "peer-named-power-input-all-open-control": "437224399056a521542a4ff556900b696250f3ad6d8fd6f7d66f24227c20d136",
    "connector-named-power-input-open-fault": "48eae0285f76c61668dbe58e33ee00bf9480a3064f5a45c2e122b12d2f91ec7c",
    "connector-named-power-input-open-control": "401fda583c25519540d427b1e24e320e5843c3aab5e99407378497e7dc475717",
    "connector-named-power-input-all-open-fault": "b17443d0e3db891ca9946f032561dabe57d29e17bd9396668b0398a70ac2fdeb",
    "connector-named-power-input-divergent-fault": "fcbe8aba85c991d73f2daa19443749a440b7eef8cb5532ec3e2d09352b6d998c",
    "connector-named-power-output-open-fault": "ef721f666d540f3ce99598fcf9e52a494729e6cdbd56b57798fd260c10bc40be",
    "connector-named-power-output-open-control": "e5621a2b8f8660db341ffe5a4088c1b802c28d1b624e522434516f0235de7d71",
    "connector-named-power-output-all-open-fault": "e16ae20d4f198fdf648049f7571bdf4db0842518bd54f8c7536d89655e93b12b",
    "connector-named-power-output-divergent-fault": "915340d72ad323d01266b90948d8a42fb55bd0879ceb74cea9b71a667f5a649a",
    "component-peer-assignment-outlier-fault": "2235639e107cfe4b060c052069c5c2bbc2a48dbef40c2bb22c8219ad6f19e7ba",
    "component-peer-assignment-outlier-control": "22f1efb0f7df6458d4523c79bc6b1e5cdd31b57463b8072cd4002105106179dc",
}
