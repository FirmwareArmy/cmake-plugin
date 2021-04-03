#include <main.h>
#include <board.h>
#include <jtag.h>

#include <core++/SysTick.h>
#include <core++/Osc8M.h>
#include <core++/PortPin.h>
#include <core++/GclkGen.h>
#include <core++/PowerManager.h>
#include <core++/Nvm.h>

#include <core++/debug.h>

#include <stringstream.h>

#include <cstring>
#include <string.h>
#include <aes.hpp>
#include <crc.h>

#include <bootloader.h>

//#define SECURE_FIRMWARE 1

void reset() ;
void run_firmware() ;
void reset_and_run_firmware() ;
int receive_firmware(uint8_t* data, core::usb_size_t size) ;
void usb_receive(uint8_t* data, core::usb_size_t size) ;
void erase_flash() ;

// in case of a controlled reset we leave remnant value as memory keeps its state between two software resets
extern int _end ;	// end of ram, defined by linker script
static volatile uint32_t *bootloader_status=(volatile uint32_t*)(&_end) ;
#define BOOTLOADER_RUN_FIRMWARE 0x16730

// firmware metadata
uint8_t* metadata=nullptr ;

// bootloader metadata
const char* bootloader_version="1.0.0" ;
char* firmware_version="Unknown" ;
uint32_t firmware_idvendor=0x0000 ;
uint32_t firmware_idproduct=0x0000 ;
uint32_t firmware_bcdDevice=0x0000 ;
char* firmware_manufacturer="Unknown" ;
char* firmware_product="Unknown" ;
const uint8_t ctr_key[33]="rsa key here                    " ;

// bootloader memory
#define bootloader_size 32768ul
const void* firmware_addr=(void*)bootloader_size ;

// indicates that somthing is listening on usb and asked for the bootloader console
bool enter_console=false ;

// bootloader console commands
enum class command_type_t : uint8_t {
	BootloaderVersion=0x0,
	FirmwareVersion=0x1,
	DeviceId=0x2,

	LoadFirmware=0x10,
	Reset=0x11,
	RunFirmware=0x12,
	EraseFlash=0x13,

	ConnectBootloader=0xFF
} ;

// finite state machines
enum class state_console_t : uint8_t {
	ReadCommand,
	LoadFirmware
} ;
state_console_t state_console=state_console_t::ReadCommand ;

enum class state_receive_fw_t : uint8_t {
	ReadSize,
	ReadIv,
	ReadData
} ;
state_receive_fw_t state_receive_fw=state_receive_fw_t::ReadSize ;

// USB retur code constants
const uint8_t USBOk=0x00 ;
const uint8_t USBError=0xFF ;

uint8_t* find_metadata()
{
	uint8_t* start=(uint8_t*)bootloader_size ;
	const uint8_t* end=(uint8_t*)(core::PAGE_SIZE*core::PAGES) ;

	while(start<end)
	{
		if(*(uint32_t*)start==METADATA_KEY0 && *(uint32_t*)start==METADATA_KEY1)
			return start ;

		// metadata block is aligned on a page start making it easier to find
		start += core::PAGE_SIZE ;
	}
	return nullptr ;
}

uint8_t* metadata_find_key(uint8_t key)
{
	const uint8_t* end=(uint8_t*)(core::PAGE_SIZE*core::PAGES) ;

	if(metadata==nullptr)
		return nullptr ;

	uint8_t* m=metadata+8 ;	// metadata starts after identification keys
	while(m<end && *m!=0 && *m<=KEY_COUNT)
	{
		if(*m==key)
			return m+2 ;
		else
			m += *(m+1) ;
	} ;

	return nullptr ;
}

char* metadata_get_string(uint8_t key, char* default_value)
{
	uint8_t* value=metadata_find_key(key) ;
	if(value!=nullptr)
		return (char*)value+2 ;

	return default_value ;
}

uint32_t metadata_get_int(uint8_t key, uint32_t default_value)
{
	uint8_t* value=metadata_find_key(key) ;
	if(value!=nullptr)
		return *(uint32_t*)(value+2) ;

	return default_value ;
}

void update_metadata()
{
	metadata = find_metadata() ;
	firmware_version = metadata_get_string(KEY_VERSION, firmware_version) ;
	firmware_idvendor = metadata_get_int(KEY_IDVENDOR, firmware_idvendor) ;
	firmware_idvendor = metadata_get_int(KEY_IDPRODUCT, firmware_idvendor) ;
	firmware_idvendor = metadata_get_int(KEY_MANUFACTURER, firmware_idvendor) ;
	firmware_version = metadata_get_string(KEY_PRODUCT, firmware_version) ;
}

void setup()
{
	// after a power on reset the bootloader should be run
	if(core::PM->RCAUSE.bit.POR)
		*bootloader_status = 0 ;

	// bootloader is asked to run firmware directly
	if(core::PM->RCAUSE.bit.SYST && *bootloader_status==BOOTLOADER_RUN_FIRMWARE)
	{
		*bootloader_status = 0 ;
		run_firmware() ;
	}

	// load metadata prior to initiliaze USB
	update_metadata() ;

	board_init() ;
//	board_init_static() ;

	enable_jtag() ;
}

#	ifdef DEBUG_BOOTLOADER
uint8_t i=0 ;
#	endif

void usb_receive(uint8_t* data, core::usb_size_t size)
{
#	ifdef DEBUG_BOOTLOADER
	print("receive ") ;
	for(int i=0 ; i<size ; i++)
		print(hex8(data[i]) << " ") ;
	print("\n") ;

	print("state " << (uint32_t)state << "\n") ;
#	endif

	switch(state_console)
	{
	case state_console_t::ReadCommand:
	{
		command_type_t* command=(command_type_t*)data ;
		switch(*command)
		{
		case command_type_t::BootloaderVersion:
			usb.write((uint8_t*)bootloader_version, strlen(bootloader_version)) ;
			break ;
		case command_type_t::FirmwareVersion:
			usb.write((uint8_t*)bootloader_version, strlen(firmware_version)) ;
			break ;
		case command_type_t::DeviceId:
		{
			core::Nvm::serial_number_t id=core::Nvm::serial_number() ;
			char s[]="00000000-00000000-00000000-00000000" ;
			StringStream st(s, sizeof(s)) ;
			st << hex32(id.word3) << "-" << hex32(id.word2) << "-" << hex32(id.word1) << "-" << hex32(id.word0) ;
			usb.write((uint8_t*)s, sizeof(s)) ;
			break ;
		}

		case command_type_t::LoadFirmware:
			state_console = state_console_t::LoadFirmware ;
			usb.write(&USBOk, 1) ;
			break ;

		case command_type_t::EraseFlash:
			erase_flash() ;
			usb.write(&USBOk, 1) ;
			break ;

		case command_type_t::Reset:
			*bootloader_status = 0 ;
			usb.write(&USBOk, 1) ;
			reset() ;
			break ;
		case command_type_t::RunFirmware:
			usb.write(&USBOk, 1) ;
			reset_and_run_firmware() ;
			break ;

		case command_type_t::ConnectBootloader:
//			if(enter_console==true)
//				reset() ;	// we do not allow multiple connections
			enter_console = true ;
			break ;
		}
		break ;
	}
	case state_console_t::LoadFirmware:
		switch(receive_firmware(data, size))
		{
		case -1:
			usb.write(&USBError, 1) ;	// there was an error
			state_console = state_console_t::ReadCommand ;
			state_receive_fw = state_receive_fw_t::ReadSize ;
			break ;
		case 0:
			usb.write(&USBOk, 1) ;	// ok to continue
			break ;
		case 1:
			// load firmware metadata
			update_metadata() ;
			usb.write(&USBOk, 1) ;	// load firmware ok
			state_console = state_console_t::ReadCommand ;
			state_receive_fw = state_receive_fw_t::ReadSize ;
			break ;
		}
		break ;
	default:
		usb.write(&USBError, 1) ;	// unknow command
		break ;
	}
}

#ifdef SECURE_FIRMWARE
// TODO add timeout
int receive_firmware(uint8_t* data, core::usb_size_t size)
{
	static uint32_t firmware_size=0 ;
	static uint32_t read_size=0 ;
	static uint16_t* flash_addr=(uint16_t*)firmware_addr ;

	static uint32_t crc=0 ;
	static AES_ctx ctx ;

	static uint32_t crc_table[256] ;

	erase_flash() ;

	switch(state_receive_fw)
	{
	case state_receive_fw_t::ReadSize:
		if(size!=4)
			return -1 ;	// protocol error
		firmware_size = *(uint32_t*)data ;
		read_size = 0 ;
		flash_addr = (uint16_t*)firmware_addr ;

		// init crc
		make_crc_table(crc_table) ;	// crc table takes 1k of flash if used static
		crc = crc32(0L, NULL, 0, crc_table) ;

		state_receive_fw = state_receive_fw_t::ReadIv ;
#		ifdef DEBUG_BOOTLOADER
		print("firmware_size:" << firmware_size << "\n") ;
#		endif
		break ;
	case state_receive_fw_t::ReadIv:
		if(size!=16)
			return -1 ;	// protocol error

		// init crypto context with stored crypto key and received iv
	    AES_init_ctx_iv(&ctx, ctr_key, data) ;

	    state_receive_fw = state_receive_fw_t::ReadData ;
		break ;
	case state_receive_fw_t::ReadData:
		if(size<4)
			return -1 ;	// protocol error

		// decrypt data
		AES_CTR_xcrypt_buffer(&ctx, data, size) ;

		// compute crc
		crc = crc32(crc, data+4, size-4, crc_table) ;

		if(*((uint32_t*)data)!=crc)
		{
			erase_flash() ;
			return -1 ;	// protocol error
		}

	    // write received data to flash
		size -= 4 ;
		data += 4 ;
		while(size>0)
		{
			*(uint16_t*)flash_addr = *(uint16_t*)data ;
			flash_addr += 2 ;
			data += 2 ;
			size -= 2 ;
		}
		read_size += size ;

		if(read_size>=firmware_size)
			return 1 ;
		break ;
	}

	return 0 ;
}
#else
bool receive_firmware(uint8_t* data, core::usb_size_t size)
{
	static uint32_t firmware_size=0 ;
	static uint32_t read_size=0 ;
	static uint16_t* flash_addr=(uint16_t*)firmware_addr ;

	static uint32_t crc=0 ;

	erase_flash() ;

	switch(state_receive_fw)
	{
	case state_receive_fw_t::ReadSize:
		if(size!=4)
			return -1 ;	// protocol error
		firmware_size = *(uint32_t*)data ;
		read_size = 0 ;
		flash_addr = (uint16_t*)firmware_addr ;

//		// init crc
//		make_crc_table(crc_table) ;	// crc table takes 1k of flash if used static
//		crc = crc32(0L, NULL, 0, crc_table) ;

		state_receive_fw = state_receive_fw_t::ReadData ;
#		ifdef DEBUG_BOOTLOADER
		print("firmware_size:" << firmware_size << "\n") ;
#		endif
		break ;
	case state_receive_fw_t::ReadData:
		// compute crc
		crc = crc32(crc, data+4, size-4, crc_table) ;

	    // write received data to flash
		while(size>0)
		{
			*(uint16_t*)flash_addr = *(uint16_t*)data ;
			flash_addr += 2 ;
			data += 2 ;
			size -= 2 ;
		}
		read_size += size ;

		// TODO check crc
		if(read_size>=firmware_size)
			return 1 ;
		break ;
	}
z
	return 0 ;
}
#endif

volatile bool sent=false ;
void transfer_complete(const uint8_t* buff)
{
	sent = true ;
}


void reset()
{
	NVIC_SystemReset() ;
}

void run_firmware()
{
#	ifdef DEBUG_BOOTLOADER
	print("run firmware\n") ;
#	endif

	// Rebase the Stack Pointer
	__set_MSP(*(uint32_t*)bootloader_size) ;

	// Rebase the vector table base address
	SCB->VTOR = bootloader_size & SCB_VTOR_TBLOFF_Msk ;

	// Jump to application Reset Handler in the application
	uint32_t app_start_address = *(uint32_t*)((uint8_t*)bootloader_size + 4) ;
	asm("bx %0"::"r"(app_start_address)) ;
}

void reset_and_run_firmware()
{
	// runing directly the firmware can cause problem if firmware does not init properly, we add an intermediate reset
	*bootloader_status = BOOTLOADER_RUN_FIRMWARE ;
	reset() ;
}

void erase_flash()
{
#		ifdef DEBUG_BOOTLOADER
		print("erase flash\n") ;
#		endif

	for(int row=bootloader_size/core::PAGE_SIZE/core::ROW_PAGES ; row<core::PAGES/core::ROW_PAGES ; row++)
		core::Nvm::erase_row(row) ;

	update_metadata() ;
}

void loop()
{
	led.set_output_value(true) ;
	core::SysTick::delay_ms(100) ;
	led.set_output_value(false) ;

#	ifdef DEBUG_BOOTLOADER
	print("bootloader\n") ;
#	endif

#	ifdef DEBUG_BOOTLOADER
	print("size: " << (uint32_t)bootloader_size << "\n") ;
	// Output main clock to check we have 48MHz
	core::PortPin clk48MHz(core::pin_t::PA14) ;	// GCLK0 output pin
	// configure pin to act as clock output
	// enable_output must be set on GCLK0
	clk48MHz.init_mux({
		.mux = core::mux_position_t::H
	}) ;
	core::GclkGen clk_main(core::gclk_gen_t::GCLK0) ;
	print( "Frequency: " << (uint32_t)clk_main.get_frequency() << "\n") ;
#	endif

	// init usb
	usb.set_receive_callback(usb_receive) ;
	usb.set_transfer_complete_callback(transfer_complete) ;
	usb.init({
		.run_in_standby = true,
		.enable 		= true
	}) ;

	// wait usb ready for 2s
	uint32_t timeout=core::SysTick::counter()+core::SysTick::ticks_per_second()*2 ;
	while(usb.ready()==false && core::SysTick::counter()<timeout)
		;

	if(usb.ready()==false)
	{
		// branch to firmware
#		ifdef DEBUG_BOOTLOADER
		print("firmware\n") ;
#		endif
		// runing directly the firmware can cause problem if firmware does not init properly, we add an intermediate reset
		reset_and_run_firmware() ;
	}
	else
	{
		// branch to console
#		ifdef DEBUG_BOOTLOADER
		print("bootloader console\n") ;
#		endif

		// wait 1s for firmware tool to connect to usb
		core::SysTick::delay_ms(2000) ;
//		uint8_t cpt=4 ;
//		while(cpt>0 && enter_console==false)
//		{
//			core::SysTick::delay_ms(1000) ;
//			cpt-- ;
//		}
		if(enter_console)
		{
			while(true)
			{
				core::SysTick::delay_ms(1000) ;
				led.toggle_output_value() ;
			}
		}
		else
		{
			// no firmware tool connected to usb
			reset_and_run_firmware() ;
		}
	}
}
