#![cfg_attr(not(feature = "std"), no_std, no_main)]

#[ink::contract]
pub mod abc {
    use ink::storage::Mapping;
    use scale::{Decode, Encode};
    use primitive_types::U256;
    #[ink(event)]
    #[derive(Debug)]
    #[cfg_attr(feature = "std", derive(Eq, PartialEq))]
    pub struct Swapped {
        pub index_in: u32,
        pub amount_in: u128,
        pub amount_out: u128,
        #[ink(topic)]
        pub who: AccountId,
    }

    #[derive(Debug, PartialEq, Eq, Encode, Decode)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub enum Error {
        NotEnoughBalance,
        WrongIndex,
        Math,
    }

    #[ink(storage)]
    pub struct Contract {
        balances: Mapping<(AccountId, u32), u128>,
        pool_balances: [u128; 2],
    }

    impl Contract {
        #[ink(constructor)]
        pub fn new(balance_0: u128, balance_1: u128, holding: u128) -> Self {
            let mut balances = Mapping::new();
            let caller = Self::env().caller();
            balances.insert((caller, 0), &holding);
            balances.insert((caller, 1), &holding);
            Self {
                balances,
                pool_balances: [balance_0, balance_1],
            }
        }

        fn increase_balance(
            &mut self,
            who: AccountId,
            index: u32,
            amount: u128,
        ) -> Result<(), Error> {
            let balance = self.balances.get(&(who, index)).unwrap_or(0);
            let balance = balance.checked_add(amount).ok_or(Error::Math)?;
            self.balances.insert(&(who, index), &balance);
            Ok(())
        }

        fn decrease_balance(
            &mut self,
            who: AccountId,
            index: u32,
            amount: u128,
        ) -> Result<(), Error> {
            let balance = self.balances.get(&(who, index)).unwrap_or(0);
            let balance = balance.checked_sub(amount).ok_or(Error::Math)?;
            self.balances.insert(&(who, index), &balance);
            Ok(())
        }

        #[ink(message)]
        pub fn swap(&mut self, amount_in: u128, index_in: u32) -> Result<(), Error> {
            let caller = self.env().caller();
            if index_in > 1 {
                return Err(Error::WrongIndex);
            }
            let index_out = 1 - index_in;
            self.decrease_balance(caller, index_in, amount_in)?;

            let balance_in_before = U256::from(self.pool_balances[index_in as usize]);
            let balance_out_before = U256::from(self.pool_balances[index_out as usize]);
            let amount_out = balance_out_before.saturating_sub(
                balance_in_before
                    .checked_mul(balance_out_before)
                    .ok_or(Error::Math)?
                    .checked_div(balance_in_before.checked_add(amount_in.into()).ok_or(Error::Math)?)
                    .ok_or(Error::Math)?,
            );
            self.increase_balance(caller, index_out, amount_out.try_into().map_err(|_| Error::Math)?)?;
            self.pool_balances[index_in as usize] = balance_in_before.checked_add(amount_in.into()).ok_or(Error::Math)?.try_into().map_err(|_| Error::Math)?;
            self.pool_balances[index_out as usize] = balance_out_before.checked_sub(amount_out.into()).ok_or(Error::Math)?.try_into().map_err(|_| Error::Math)?;
            self.env().emit_event(Swapped {
                index_in,
                amount_in,
                amount_out: amount_out.try_into().map_err(|_| Error::Math)?,
                who: caller,
            });
            Ok(())
        }
    }
}
