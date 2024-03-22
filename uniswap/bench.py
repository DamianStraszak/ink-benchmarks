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


def read_call(name, instance, method, args, keypair):
    res = instance.read(keypair = keypair,method = method, args=args).value
    return res['result']['Ok']['data']['Ok']




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



def print_balances(token_dir_name, tokens, dummy):
    for num in range(3):
        balance_alice = read_call(token_dir_name, tokens[num], "PSP22::balance_of", {"owner": dummy.ss58_address}, dummy)
        print(f"Balance of Alice in token {num} = {balance_alice}")

def instantiate_tokens(chain, token_dir_name):
    return [instantiate_contract(chain, token_dir_name, "contract", "new", args={"total_supply": 10*1000000, "name": f"token-{num}", "symbol": f"token-{num}", "decimals": 6}) for num in range(3)]




def bench_uniswap_multipool():
    
    dex_dir_name = "uniswap-multipool"
    contract_name = "contract"
    token_dir_name = "mintable-psp22"

    print(f"Compiling {dex_dir_name}")
    compile_contract(dex_dir_name, contract_name)
    print(f"Compiling {token_dir_name}")
    compile_contract(token_dir_name, contract_name)
    mil = 1000000
    chain = SubstrateInterface(
        url=WS_ENDPOINT
    )
    dummy = Keypair.create_from_uri('//Alice')
    dex_instance = instantiate_contract(chain, dex_dir_name, contract_name, "new", args={})
    tokens = instantiate_tokens(chain, token_dir_name)
    token_addresses = [token.contract_address for token in tokens]
    # {token_0: AccountId, balance_0: u128,  token_1: AccountId, balance_1:u128, fee: u32}
    for token in tokens:
        test_call(token_dir_name, token, "PSP22::approve", {"spender": dex_instance.contract_address, "value": 100*mil}, dummy)

    print_balances(token_dir_name, tokens, dummy)

    print("Testing PSP22::transfer")

    test_call(token_dir_name, tokens[0], "PSP22::transfer", {"to": Keypair.create_from_uri('//Bob').ss58_address, "value": 1*mil, "_data": []}, dummy)

    print_balances(token_dir_name, tokens, dummy)

    new_pool_args = {"token_0": token_addresses[0], "balance_0": 5*mil, "token_1": token_addresses[1], "balance_1": 5*mil, "fee": 30}
    test_call(dex_dir_name, dex_instance, "new_pool", new_pool_args, dummy)

    print_balances(token_dir_name, tokens, dummy)

    new_pool_args = {"token_0": token_addresses[1], "balance_0": 5*mil, "token_1": token_addresses[2], "balance_1": 5*mil, "fee": 30}
    test_call(dex_dir_name, dex_instance, "new_pool", new_pool_args, dummy)

    print_balances(token_dir_name, tokens, dummy)

    # swap(&mut self, token_in: AccountId, token_out: AccountId, amount_in: u128, min_amount_out: u128, pools: Vec<u32>) 
    print("Swapping token 0 for token 1")
    swap_args = {"token_in": token_addresses[0], "token_out": token_addresses[1], "amount_in": mil, "min_amount_out": 0, "pools": [0]}
    test_call(dex_dir_name, dex_instance, "swap", swap_args, dummy)

    print_balances(token_dir_name, tokens, dummy)

    # swap(&mut self, token_in: AccountId, token_out: AccountId, amount_in: u128, min_amount_out: u128, pools: Vec<u32>) 
    print("Swapping token 0 for token 1 for token 2")
    swap_args = {"token_in": token_addresses[0], "token_out": token_addresses[2], "amount_in": mil, "min_amount_out": 0, "pools": [0, 1]}
    test_call(dex_dir_name, dex_instance, "swap", swap_args, dummy)

    print_balances(token_dir_name, tokens, dummy)
    


if __name__ == "__main__":
    print("Basic uniswap without u256")
    bench_uniswap("uniswap-internal", "contract")
    print("\n\n\nBasic uniswap with u256")
    bench_uniswap("uniswap-internal-u256", "contract")
    print("\n\n\nMultipool uniswap")
    bench_uniswap_multipool()


    

   