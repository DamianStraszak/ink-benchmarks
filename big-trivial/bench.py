import time
import random
import subprocess
import csv
from substrateinterface import ContractInstance, Keypair, SubstrateInterface, ContractCode, ContractMetadata

contract_name = "trivial"

def salt():
    return str(time.time())

def weight():
    return {'ref_time': 25990000000, 'proof_size': 119903}

def generate_contract(n):
    code = "let a0: u128 = x;\n"
    c = 111111
    for i in range(n):
        if i>0:
            # coin toss
            if 0 == random.randint(0, 2):
                code += f"let a{i} = a{i-1}.saturating_add({c+i});\n"
            else:
                code += f"let a{i} = a{i-1}.saturating_sub({c//3+i//4});\n"
    code += f"self.val = a{n-1};\n"

    # Reads the trivial/pattern.rs file and replaces the `FILL_HERE` pattern with code, then saves it under trivial/lib.rs
    with open(f"{contract_name}/pattern.rs", "r") as file:
        data = file.read()
    data = data.replace("FILL_HERE", code)
    with open(f"{contract_name}/lib.rs", "w") as file:
        file.write(data)

def compile_contract():
    cmd = f"cd {contract_name} && cargo contract build --release"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    assert result.returncode == 0, f"Command failed with return code {result.returncode}"
    #print(result)
    # prints size of the file /trivial/target/ink/trivial.wasm
    path = f"ls -l {contract_name}/target/ink/{contract_name}.wasm"
    result = subprocess.run(path+" | awk '{print $5}'", shell=True, text=True, capture_output=True)  
    file_size = int(result.stdout)
    print(f"n={n}, size={file_size}")  
    return file_size


def bench(n):
    generate_contract(n)
    #time.sleep(1)
    file_size = compile_contract()

    chain = SubstrateInterface(
        url="ws://localhost:9944",
    )

    dummy = Keypair.create_from_uri('//Alice')

    contract_code = ContractCode.create_from_contract_files(f"{contract_name}/target/ink/{contract_name}.wasm", f"{contract_name}/target/ink/{contract_name}.json", substrate=chain)


    print(f"Deploying {contract_name} contract")
    instance = contract_code.deploy(keypair=dummy, constructor="new", args={"init_value":0},deployment_salt=salt(), gas_limit = weight(), upload_code=True)


    res=instance.read(keypair = dummy,method = "store", args={"new_value":1000}).value
    gas = res['gas_consumed']
    print(f"Dry-run gas {gas}")
    dry_run_gas = gas["ref_time"]



    res = instance.exec(keypair = dummy,method = "store", args={"new_value":1000})
    fee = res.total_fee_amount
    print(f"Actual fee used {fee}")

    return (file_size, dry_run_gas, fee)


if __name__ == "__main__":
    data = []
    for n in range(1, 15003, 2500):
        data += [bench(n)]

    csv_file_path = 'data.csv'

    # Writing data to CSV
    with open(csv_file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["wasm size", "dry-run", "fee"])  # Writing headers
        writer.writerows(data) 


    

   