# USR TCP232 Monitor – Home Assistant Custom Component

[![GitHub Release](https://img.shields.io/github/v/release/LukaszP2/usr_tcp232_monitor?style=flat-square)](https://github.com/LukaszP2/usr_tcp232_monitor/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)


[![Otwórz repozytorium w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukaszP2&repository=usr_tcp232_monitor&category=integration)
[![Dodaj integrację do Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=usr_tcp232_monitor)

*(🇬🇧 English description below)*

---

## 🇵🇱 Opis

Lokalna integracja diagnostyczno-monitoringowa dla konwerterów sieciowych Ethernet/RS485 USR-TCP232 (USR-IoT).

### Główne funkcje
- Lokalne odpytywanie urządzeń po sieci LAN (brak zależności od chmury)
- Status połączenia, czas pracy (uptime), statystyki pakietów TX/RX
- Monitorowanie osiągalności panelu WWW i stanu bramy MQTT
- Sensory diagnostyczne i binarne

### Instalacja przez HACS (Niestandardowe repozytorium)

### 🚀 Szybka instalacja (1 kliknięcie przez My Home Assistant)

[![Otwórz repozytorium w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukaszP2&repository=usr_tcp232_monitor&category=integration)

Po zainstalowaniu i ponownym uruchomieniu Home Assistant, kliknij poniższy przycisk, aby skonfigurować integrację:

[![Dodaj integrację do Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=usr_tcp232_monitor)



1. Upewnij się, że masz zainstalowany **HACS** w Home Assistant.
2. W HACS przejdź do: **Integracje** -> menu w prawym górnym rogu (trzy kropki) -> **Niestandardowe repozytoria** (*Custom repositories*).
3. W polu **Repozytorium** wklej adres:
   ```text
   https://github.com/LukaszP2/usr_tcp232_monitor
   ```
4. W polu **Kategoria** wybierz: **Integracja** (*Integration*).
5. Kliknij **Dodaj**, a następnie wyszukaj **USR TCP232 Monitor** i kliknij **Pobierz**.
6. Uruchom ponownie Home Assistant.

### Konfiguracja

1. W Home Assistant przejdź do: **Ustawienia** -> **Urządzenia oraz usługi** -> **Dodaj integrację**.
2. Wyszukaj **USR TCP232 Monitor**.
3. Postępuj zgodnie z instrukcjami na ekranie.

### 📋 Gotowe Blueprinty automatyzacji

W repozytorium przygotowane są gotowe szablony automatyzacji (w katalogu `blueprints/automation/usr_tcp232_monitor/`):
- **Alert o utracie łączności z konwerterem** (`gateway_offline_alert.yaml`) – powiadamia o braku odpowiedzi panelu WWW i opcjonalnie informuje o przywróceniu połączenia.
- **Utrata sesji TCP portu szeregowego** (`port_disconnect_alert.yaml`) – monitoruje status sesji TCP portu szeregowego (np. z integracją Modbus) i powiadamia o rozłączeniu.
- **Wykrycie restartu konwertera** (`unexpected_reboot_alert.yaml`) – wykrywa nagłe spadki czasu pracy (runtime), identyfikując zaniki zasilania lub zadziałanie watchdoga.
- **Wykrycie braku transmisji na magistrali szeregowej** (`serial_traffic_stall.yaml`) – ostrzega przed zamrożeniem transmisji danych (brak przyrostu liczników TX/RX) z opcjonalnym filtrem godzinowym.
- **Automatyczny restart zasilania przy zawieszeniu** (`auto_heal_power_cycle.yaml`) – automatyczny cykl zasilania (smart plug/przekaźnik) przy trwałej niedostępności konwertera z ochroną przed pętlą restartów.

---

## 🇬🇧 Description

Local monitoring and diagnostic integration for USR-TCP232 Ethernet-to-Serial RS485/RS232 converter modules.

### Installation via HACS (Custom Repository)

1. Open **HACS** in Home Assistant.
2. Navigate to **Integrations** -> top right menu (three dots) -> **Custom repositories**.
3. Enter repository URL:
   ```text
   https://github.com/LukaszP2/usr_tcp232_monitor
   ```
4. Category: **Integration**.
5. Click **Add**, find **USR TCP232 Monitor**, and install.
6. Restart Home Assistant.

### 📋 Ready-to-use Automation Blueprints

Available in `blueprints/automation/usr_tcp232_monitor/`:
- **Gateway Offline Alert** (`gateway_offline_alert.yaml`) – notifies when web interface is unreachable and optionally on recovery.
- **Serial Port TCP Disconnection** (`port_disconnect_alert.yaml`) – monitors serial port TCP state and notifies when disconnected.
- **Unexpected Reboot Alert** (`unexpected_reboot_alert.yaml`) – detects sudden runtime drops indicating power loss or watchdog triggers.
- **Serial Traffic Stall Alert** (`serial_traffic_stall.yaml`) – warns when RX/TX byte counters freeze with optional time window filtering.
- **Auto-Heal Power Cycle** (`auto_heal_power_cycle.yaml`) – automated power-cycle recovery via smart plug with anti-loop cooldown.

---

## Licencja / License

Projekt objęty licencją [MIT](LICENSE).