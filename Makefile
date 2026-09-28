.PHONY: build verify deploy sync-media fetch-media

# Kubeconfig ligger uden for alle repos (skrives af infra's ansible-playbook).
# Overstyr med KUBECONFIG=... hvis du har den et andet sted.
KUBECONFIG ?= $(HOME)/.kube/gihc.yml
export KUBECONFIG

# deploy.sh sætter BUILD_FLAGS=--strict-media, så et deploy afbrydes hvis
# medierne mangler lokalt. Til manuel inspektion kan den stå tom.
BUILD_FLAGS ?=

build:
	python3 build.py $(BUILD_FLAGS)
	cp logo/logo-symmetrisk.svg k8s/logo.svg
	convert -background white -density 300 logo/logo-symmetrisk.svg -resize '1024x1024>' -gravity center -extent 1024x1024 -strip k8s/logo.png

verify: build
	python3 -c "import xml.etree.ElementTree as ET, build; [ET.parse(f.output) for f in build.FEEDS]; print(f'feeds: gyldig XML ({len(build.FEEDS)})')"
	file k8s/logo.png | grep -q "PNG image data" && echo "logo.png: ok"

deploy:
	bash scripts/deploy.sh

sync-media:
	POD=$$(kubectl -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}'); \
	kubectl cp media/ higgs/$$POD:/usr/share/nginx/html/

# Media er ikke i git: hent dem over HTTPS på en ny maskine.
fetch-media:
	python3 scripts/fetch-media.py
