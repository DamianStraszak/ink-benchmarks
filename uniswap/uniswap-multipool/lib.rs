#![cfg_attr(not(feature = "std"), no_std, no_main)]



#[ink::contract]
pub mod abc {
    use ink::storage::Mapping;
    use scale::{Decode, Encode};
    use primitive_types::U256;
    use psp22::PSP22;
    use ink::prelude::{vec, vec::Vec};
    #[ink(event)]
    #[derive(Debug)]
    #[cfg_attr(feature = "std", derive(Eq, PartialEq))]
    pub struct Swapped {
        pub token_in: AccountId,
        pub token_out: AccountId,
        pub amount_in: u128,
        pub amount_out: u128,
        #[ink(topic)]
        pub who: AccountId,
    }

    const FEE_DENOMINATOR: u32 = 10000;

    #[derive(Debug, PartialEq, Eq, Encode, Decode)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub enum Error {
        NotEnoughBalance,
        WrongIndex,
        Math,
        EqualTokens,
        PoolAlreadyExists,
        PSP22Error,
        WrongFee,
        WrongSwapArgs,
        ReceivedTooLowAmount
    }

    #[derive(PartialEq, Debug, Clone, scale::Decode, scale::Encode)]
#[cfg_attr(
    feature = "std",
    derive(scale_info::TypeInfo, ink::storage::traits::StorageLayout)
)]
    struct Pool {
        fee: u32,
        total_shares: u128,
        tokens: [AccountId; 2],
        balances: [u128; 2],
    }

    pub fn casted_mul(a: u128, b: u128) -> U256 {
        U256::from(a) * U256::from(b)
    }

    #[ink(storage)]
    pub struct Contract {
        pool_counter: u32,
        pools: Mapping<u32, Pool>,
    }

    impl Contract {
        #[ink(constructor)]
        pub fn new() -> Self {
            Self {
                pool_counter: 0,
                pools: Mapping::new(),
            }
        }

        fn mint_shares(&mut self, _caller: AccountId, _amount: u128) -> Result<(), Error> {
            Ok(())
        }


        #[ink(message)]
        pub fn new_pool(&mut self, token_0: AccountId, balance_0: u128,  token_1: AccountId, balance_1:u128, fee: u32) -> Result<(), Error> {
            if token_0 == token_1 {
                return Err(Error::EqualTokens);
            }
            if balance_0 == 0 || balance_1 == 0 {
                return Err(Error::NotEnoughBalance);
            }
            if fee==0 || fee >= FEE_DENOMINATOR {
                return Err(Error::WrongFee);
            }
            for (token, balance) in &[(token_0, balance_0), (token_1, balance_1)] {
                let mut psp22: ink::contract_ref!(PSP22) = (*token).into();
                psp22.transfer_from(self.env().caller(), self.env().account_id(), *balance, vec![]).map_err(|_| Error::PSP22Error)?;
            }
            let shares_amount = casted_mul(balance_0, balance_1).integer_sqrt().try_into().map_err(|_| Error::Math)?;
            // TODO: Need to create a token for the LP shares
            self.mint_shares(self.env().caller(), shares_amount).map_err(|_| Error::PSP22Error)?;


            self.pools.insert(self.pool_counter, &Pool { total_shares: shares_amount, tokens: [token_0, token_1], balances: [balance_0, balance_1], fee });
            self.pool_counter += 1;
            Ok(())
        }


        #[ink(message)]
        pub fn provide_liquidity(&mut self, pool_index: u32, balance_0: u128, balance_1:u128) -> Result<(), Error> {
            let mut pool = self.pools.get(pool_index).ok_or(Error::WrongIndex)?;
            if balance_0 == 0 || balance_1 == 0 {
                return Err(Error::NotEnoughBalance);
            }
            let mut shares = u128::MAX;
            for (i, balance_in) in [balance_0, balance_1].iter().enumerate() {
                let token = pool.tokens[i];
                let mut psp22: ink::contract_ref!(PSP22) = token.into();
                psp22.transfer_from(self.env().caller(), self.env().account_id(), *balance_in, vec![]).map_err(|_| Error::PSP22Error)?;
                let pool_token_balance = pool.balances[i];
                let maybe_shares = casted_mul(*balance_in, pool.total_shares).checked_div(U256::from(pool_token_balance)).ok_or(Error::Math)?.try_into().map_err(|_| Error::Math)?;
                pool.balances[i] = pool_token_balance.checked_add(*balance_in).ok_or(Error::Math)?;
                shares = shares.min(maybe_shares);
            }
            self.mint_shares(self.env().caller(), shares).map_err(|_| Error::PSP22Error)?;
            Ok(())
        }

        fn swap_in_pool(&mut self, token_in: AccountId, amount_in: u128, pool_index: u32) -> Result<(AccountId, u128), Error> {
            let mut pool = self.pools.get(pool_index).ok_or(Error::WrongIndex)?;
            let index_in = pool.tokens.iter().position(|&x| x == token_in).ok_or(Error::WrongIndex)? as u32;
            let index_out = 1 - index_in;

            let balance_in_before = U256::from(pool.balances[index_in as usize]);
            let balance_out_before = U256::from(pool.balances[index_out as usize]);
            let amount_out = balance_out_before.saturating_sub(
                balance_in_before
                    .checked_mul(balance_out_before)
                    .ok_or(Error::Math)?
                    .checked_div(balance_in_before.checked_add(amount_in.into()).ok_or(Error::Math)?)
                    .ok_or(Error::Math)?,
            );
            pool.balances[index_in as usize] = pool.balances[index_in as usize].checked_add(amount_in).ok_or(Error::Math)?;
            pool.balances[index_out as usize] = pool.balances[index_out as usize].saturating_sub(amount_out.try_into().map_err(|_| Error::Math)?);
            self.pools.insert(pool_index, &pool);
            Ok((pool.tokens[index_out as usize], amount_out.try_into().map_err(|_| Error::Math)?))
        } 

        #[ink(message)]
        pub fn swap(&mut self, token_in: AccountId, token_out: AccountId, amount_in: u128, min_amount_out: u128, pools: Vec<u32>) -> Result<(), Error> {
            let caller = self.env().caller();
            let mut psp22: ink::contract_ref!(PSP22) = token_in.into();
            psp22.transfer_from(caller, self.env().account_id(), amount_in, vec![]).map_err(|_| Error::PSP22Error)?;


            let mut current_token = token_in;
            let mut current_amount = amount_in;
            for pool_index in pools {
                (current_token, current_amount) = self.swap_in_pool(current_token, current_amount, pool_index)?;
            }
            
            if current_amount < min_amount_out {
                return Err(Error::ReceivedTooLowAmount);
            }
            if current_token != token_out {
                return Err(Error::WrongSwapArgs);
            }
            let mut psp22: ink::contract_ref!(PSP22) = token_out.into();
            psp22.transfer(caller, current_amount, vec![]).map_err(|_| Error::PSP22Error)?;
            self.env().emit_event(Swapped {
                token_in,
                token_out,
                amount_in,
                amount_out: current_amount,
                who: caller,
            });
            Ok(())
        }
    }
}
