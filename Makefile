.PHONY: build verify deploy sync-media

# Kubeconfig ligger uden for alle repos (skrives af infra's ansible-playbook).
# Overstyr med KUBECONFIG=... hvis du har den et andet sted.
KUBECONFIG ?= $(HOME)/.kube/gihc.yml
export KUBECONFIG

build:
	python3 build.py
	cp logo/logo-symmetrisk.svg k8s/logo.svg
	convert -background white -density 300 logo/logo-symmetrisk.svg -resize '1024x1024>' -gravity center -extent 1024x1024 -strip k8s/logo.png

verify: build
	python3 -c "import xml.etree.ElementTree as ET; ET.parse('k8s/feed.xml'); print('feed.xml: gyldig XML')"
	file k8s/logo.png | grep -q "PNG image data" && echo "logo.png: ok"

deploy:
	bash scripts/deploy.sh

sync-media:
	POD=$$(kubectl -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}'); \
	kubectl cp media/ higgs/$$POD:/usr/share/nginx/html/
