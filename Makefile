.PHONY: build verify deploy sync-media

build:
	python3 build.py
	cp logo/logo-symmetrisk.svg k8s/logo.svg
	convert -background white -density 300 logo/logo-symmetrisk.svg -resize '1024x1024>' -gravity center -extent 1024x1024 k8s/logo.png

verify: build
	python3 -c "import xml.etree.ElementTree as ET; ET.parse('k8s/feed.xml'); print('feed.xml: gyldig XML')"
	file k8s/logo.png | grep -q "PNG image data" && echo "logo.png: ok"

deploy:
	bash scripts/deploy.sh

sync-media:
	POD=$$(kubectl --kubeconfig ../infra/kubeconfig.yml -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}'); \
	kubectl --kubeconfig ../infra/kubeconfig.yml cp media/ higgs/$$POD:/usr/share/nginx/html/
