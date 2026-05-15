
cd csi_client
make build
cd ..
cp csi_client/dist/*whl lib
pip install -r requirements.txt --force-reinstall
python tester.py
