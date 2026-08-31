.PHONY: build verify deploy sync-media

build:
	python3 build.py

verify: build
	python3 -c "import xml.etree.ElementTree as ET; ET.parse('k8s/feed.xml'); print('feed.xml: gyldig XML')"

deploy: build
	kubectl --kubeconfig ../infra/kubeconfig.yml apply -k k8s/

sync-media:
	POD=$$(kubectl --kubeconfig ../infra/kubeconfig.yml -n higgs get pod -l app=higgs -o jsonpath='{.items[0].metadata.name}'); \
	kubectl --kubeconfig ../infra/kubeconfig.yml cp media/ higgs/$$POD:/usr/share/nginx/html/
