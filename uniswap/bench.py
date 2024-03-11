import time
import random
import subprocess
import json
from substrateinterface import ContractInstance, Keypair, SubstrateInterface, ContractCode, ContractMetadata


WS_ENDPOINT = "ws://localhost:9944"

def salt():
    return str(time.time())

def weight():
    return {'ref_time': 25990000000, 'proof_size': 119903}


def compile_contract(dir_name, contract_name):
    cmd = f"cd {dir_name} && cargo contract build --release"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    assert result.returncode == 0, f"Command failed with return code {result.returncode}"
    #print(result)
    # prints size of the file /trivial/target/ink/trivial.wasm
    path = f"ls -l {dir_name}/target/ink/{contract_name}.wasm"
    result = subprocess.run(path+" | awk '{print $5}'", shell=True, text=True, capture_output=True)  
    file_size = int(result.stdout)
    print(f"Size of {dir_name} = {file_size}") 
    return file_size


def instantiate_contract(chain, dir_name, contract_name, constructor_name, args):
    dummy = Keypair.create_from_uri('//Alice')
    contract_code = ContractCode.create_from_contract_files(f"{dir_name}/target/ink/{contract_name}.wasm", f"{dir_name}/target/ink/{contract_name}.json", substrate=chain)
    print(f"Deploying {contract_name} contract")
    instance = contract_code.deploy(keypair=dummy, constructor=constructor_name, args=args,deployment_salt=salt(), gas_limit = weight(), upload_code=True)
    return instance




def test_call(name, instance, method, args, keypair):
    res = instance.read(keypair = keypair,method = method, args=args).value
    ref_time = res["gas_consumed"]["ref_time"]
    ref_time_frac = ref_time/(1e12)
    #print("Read", json.dumps(res, indent=4))

    res = instance.exec(keypair = keypair,method = method, args=args)
    fee_paid = res.total_fee_amount
    fee_paid_azero = fee_paid/1e12

    print(f"{name:20} {method:10} dry_run: {ref_time_frac:8.5f}   fee: {fee_paid_azero:8.5f}")




def bench_uniswap(dir_name, contract_name):
    print(f"Compiling {dir_name}")
    compile_contract(dir_name, contract_name)
    print(f"Deploying {dir_name}")
    mil = 1000000
    chain = SubstrateInterface(
        url=WS_ENDPOINT
    )
    instance = instantiate_contract(chain, dir_name, contract_name, "new", args={"balance_0": 10*mil, "balance_1": 10*mil, "holding": 100*mil})
    dummy = Keypair.create_from_uri('//Alice')
    test_call(dir_name, instance, "swap", {"amount_in": mil, "index_in": 0}, dummy)






if __name__ == "__main__":
    bench_uniswap("uniswap-internal", "contract")
    bench_uniswap("uniswap-internal-u256", "contract")


    

   