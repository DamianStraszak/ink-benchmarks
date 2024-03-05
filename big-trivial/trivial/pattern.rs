#![cfg_attr(not(feature = "std"), no_std, no_main)]


#[ink::contract]
mod trivial {

    #[ink(event)]
    pub struct Stored {
        val: u128,
    }

    #[ink(storage)]
    pub struct Trivial {
        val: u128,
    }

    impl Trivial {
        /// Creates a new greeter contract initialized with the given value.
        #[ink(constructor)]
        pub fn new(init_value: u128) -> Self {
            Self {
                val: init_value,
            }
        }


        #[ink(message)]
        pub fn greet(&self) -> u128 {
            self.val
        }

        #[ink(message)]
        pub fn store(&mut self, new_value: u128) {
            self.val = new_value;
            self.env().emit_event(Stored { val: new_value });
        }

        #[ink(message)]
        pub fn dummy(&mut self, x:u128) {
            FILL_HERE
        }
    }
}
